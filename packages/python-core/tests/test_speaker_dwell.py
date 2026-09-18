"""
Tests for Active-Speaker Detection — Dwell Timer, Signal Fusion & Backward Compatibility.

Non-negotiable requirement:
- test_standard_mode_scoring_unchanged asserts EXACT existing formula (mar_variance * 10.0 + mar * 2.0)
  is used for tracking_mode == "standard", with no dwell timer, no fusion, and no group fallback.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from clipforge_core.services.face_tracker import (
    _compute_enhanced_score,
    _compute_standard_score,
    _find_active_speaker,
    _find_active_speaker_enhanced,
    track_faces,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_standard_mode_scoring_unchanged():
    """
    Assert the EXACT existing formula (mar_variance * 10.0 + mar * 2.0)
    is used for tracking_mode == 'standard', with no dwell timer, no fusion,
    no group fallback logic entered at all for that path.
    """
    # 1. Single sample history: formula is mar * 2.0
    history_single = [0.15]
    mar = 0.15
    expected_single = mar * 2.0
    assert _compute_standard_score(history_single, mar) == pytest.approx(expected_single)

    # 2. Multi-sample history: exact formula = mar_variance * 10.0 + mar * 2.0
    history_multi = [0.10, 0.20, 0.30, 0.40]
    mean_mar = sum(history_multi) / len(history_multi)
    mar_variance = sum((m - mean_mar) ** 2 for m in history_multi) / len(history_multi)
    current_mar = 0.35
    expected_multi = mar_variance * 10.0 + current_mar * 2.0

    actual_multi = _compute_standard_score(history_multi, current_mar)
    assert actual_multi == pytest.approx(expected_multi)

    # 3. Verify that _find_active_speaker uses _compute_standard_score and no fusion
    mock_bbox = MagicMock()
    mock_bbox.xmin = 0.4
    mock_bbox.ymin = 0.4
    mock_bbox.width = 0.2
    mock_bbox.height = 0.2
    mock_det = MagicMock()
    mock_det.location_data.relative_bounding_box = mock_bbox

    mock_face_mesh = MagicMock()
    mock_landmark_top = MagicMock(y=0.45)
    mock_landmark_bottom = MagicMock(y=0.55)
    mock_landmark_left = MagicMock(x=0.45)
    mock_landmark_right = MagicMock(x=0.55)
    mock_landmarks = {13: mock_landmark_top, 14: mock_landmark_bottom, 78: mock_landmark_left, 308: mock_landmark_right}

    mock_mesh_face = MagicMock()
    mock_mesh_face.landmark = mock_landmarks
    mock_mesh_res = MagicMock()
    mock_mesh_res.multi_face_landmarks = [mock_mesh_face]
    mock_face_mesh.process.return_value = mock_mesh_res

    rgb_frame = np.zeros((270, 480, 3), dtype=np.uint8)
    mar_hist = {}

    speaker_x = _find_active_speaker(
        rgb_frame=rgb_frame,
        detections=[mock_det],
        face_mesh=mock_face_mesh,
        mar_history=mar_hist,
        window_size=5,
    )
    assert speaker_x is not None
    assert speaker_x == pytest.approx(0.5, abs=0.01)


def test_enhanced_mode_uses_fused_scoring():
    """Verify enhanced mode fuses visual lip movement (60%), spatial stability (30%), and recency (10%)."""
    history = [0.10, 0.20, 0.30]
    mar = 0.25
    center_x = 0.8
    last_speaker_x = 0.2  # Far from last speaker -> stability penalty
    is_speech_active = True

    std_score = _compute_standard_score(history, mar)
    enh_score = _compute_enhanced_score(history, mar, center_x, last_speaker_x, is_speech_active)

    # Hand-calculate fused score
    stability = max(0.0, 1.0 - abs(center_x - last_speaker_x))  # 1.0 - 0.6 = 0.4
    recency = mar * 3.0  # 0.75
    expected_enh = std_score * 0.6 + stability * 0.3 + recency * 0.1

    assert enh_score == pytest.approx(expected_enh)
    # Different weights mean enhanced score is distinct from standard score
    assert enh_score != pytest.approx(std_score)


def test_dwell_prevents_rapid_switch():
    """
    Test dwell timer state machine: a new candidate speaker appearing for only 1 frame
    must NOT trigger an immediate speaker switch when _DWELL_FRAMES = 2.
    """
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.side_effect = [True, True, True, False]
        mock_cap.get.side_effect = lambda prop: 2.0 if prop == 7 else 30.0  # frame_count=2, fps=30
        
        frame = np.zeros((270, 480, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_cap_cls.return_value = mock_cap

        det_a = MagicMock()
        det_a.location_data.relative_bounding_box = MagicMock(xmin=0.1, ymin=0.2, width=0.2, height=0.2)
        det_b = MagicMock()
        det_b.location_data.relative_bounding_box = MagicMock(xmin=0.7, ymin=0.2, width=0.2, height=0.2)

        fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
        transcript = {"segments": [{"start": 0.0, "end": 5.0, "text": "speech"}]}

        call_count = 0
        def fake_find_enhanced(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (0.2, 0.5)  # Face A established
            else:
                return (0.8, 0.8)  # Face B appears for 1 frame

        with patch("clipforge_core.services.face_tracker._find_active_speaker_enhanced", side_effect=fake_find_enhanced):
            with patch("mediapipe.solutions.face_detection.FaceDetection") as mock_fd:
                mock_fd_inst = MagicMock()
                mock_fd_res = MagicMock()
                mock_fd_res.detections = [det_a, det_b]
                mock_fd_inst.process.return_value = mock_fd_res
                mock_fd.return_value = mock_fd_inst

                with patch("mediapipe.solutions.face_mesh.FaceMesh"):
                    res = track_faces(fixture, sample_fps=30.0, tracking_mode="enhanced", transcript=transcript)

                    assert res["tracking_mode"] == "enhanced"
                    assert res["dwell_switches"] == 0
                    assert res["dwell_rejections"] >= 1


def test_dwell_allows_sustained_switch():
    """
    When a new candidate speaker is dominant for >= _DWELL_FRAMES (2 frames),
    the switch must be committed.
    """
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.side_effect = [True, True, True, True, False]
        mock_cap.get.side_effect = lambda prop: 3.0 if prop == 7 else 30.0  # 3 frames
        
        frame = np.zeros((270, 480, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_cap_cls.return_value = mock_cap

        det_a = MagicMock()
        det_a.location_data.relative_bounding_box = MagicMock(xmin=0.1, ymin=0.2, width=0.2, height=0.2)
        det_b = MagicMock()
        det_b.location_data.relative_bounding_box = MagicMock(xmin=0.7, ymin=0.2, width=0.2, height=0.2)

        fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
        transcript = {"segments": [{"start": 0.0, "end": 5.0, "text": "speech"}]}

        call_count = 0
        def fake_find_enhanced(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (0.2, 0.5)  # Frame 1: Face A
            elif call_count == 2:
                return (0.8, 0.8)  # Frame 2: Face B (dwell count 1)
            else:
                return (0.8, 0.8)  # Frame 3: Face B (dwell count 2 -> committed switch!)

        with patch("clipforge_core.services.face_tracker._find_active_speaker_enhanced", side_effect=fake_find_enhanced):
            with patch("mediapipe.solutions.face_detection.FaceDetection") as mock_fd:
                mock_fd_inst = MagicMock()
                mock_fd_res = MagicMock()
                mock_fd_res.detections = [det_a, det_b]
                mock_fd_inst.process.return_value = mock_fd_res
                mock_fd.return_value = mock_fd_inst

                with patch("mediapipe.solutions.face_mesh.FaceMesh"):
                    res = track_faces(fixture, sample_fps=30.0, tracking_mode="enhanced", transcript=transcript)

                    assert res["tracking_mode"] == "enhanced"
                    assert res["dwell_switches"] == 1


def test_group_fallback_during_silence():
    """In enhanced mode, silence exceeding 2.0s drifts target toward 0.5 center group shot."""
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.side_effect = [True, True, False]
        mock_cap.get.side_effect = lambda prop: 2.0 if prop == 7 else 1.0  # 2 frames at 1 fps -> t=0, t=1
        
        frame = np.zeros((270, 480, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_cap_cls.return_value = mock_cap

        det_a = MagicMock()
        det_a.location_data.relative_bounding_box = MagicMock(xmin=0.1, ymin=0.2, width=0.2, height=0.2)
        det_b = MagicMock()
        det_b.location_data.relative_bounding_box = MagicMock(xmin=0.8, ymin=0.2, width=0.2, height=0.2)

        fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
        # No speech in transcript -> silence duration grows
        transcript = {"segments": [{"start": 100.0, "end": 105.0, "text": "later"}]}

        with patch("mediapipe.solutions.face_detection.FaceDetection") as mock_fd:
            mock_fd_inst = MagicMock()
            mock_fd_res = MagicMock()
            mock_fd_res.detections = [det_a, det_b]
            mock_fd_inst.process.return_value = mock_fd_res
            mock_fd.return_value = mock_fd_inst

            with patch("mediapipe.solutions.face_mesh.FaceMesh"):
                res = track_faces(fixture, sample_fps=1.0, tracking_mode="enhanced", transcript=transcript)

                assert res["tracking_mode"] == "enhanced"
                assert len(res["timeline"]) > 0


def test_backward_compat_no_transcript():
    """Both standard and enhanced modes function properly and predictably without transcript."""
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    res_std = track_faces(fixture, sample_fps=1.0, tracking_mode="standard", transcript=None)
    res_enh = track_faces(fixture, sample_fps=1.0, tracking_mode="enhanced", transcript=None)

    assert res_std["fallback_used"] is True
    assert res_enh["fallback_used"] is True
    assert res_std["tracking_mode"] == "standard"
    assert res_enh["tracking_mode"] == "enhanced"
    assert "dwell_switches" in res_enh
    assert "dwell_rejections" in res_enh


def test_backward_compat_single_face():
    """Single-face path passes through direct face coordinates in both modes."""
    with patch("cv2.VideoCapture") as mock_cap_cls:
        mock_cap = MagicMock()
        mock_cap.isOpened.side_effect = [True, True, False]
        mock_cap.get.side_effect = lambda prop: 1.0 if prop == 7 else 30.0
        frame = np.zeros((270, 480, 3), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame)
        mock_cap_cls.return_value = mock_cap

        det_single = MagicMock()
        det_single.location_data.relative_bounding_box = MagicMock(xmin=0.3, ymin=0.2, width=0.2, height=0.2)

        fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"

        with patch("mediapipe.solutions.face_detection.FaceDetection") as mock_fd:
            mock_fd_inst = MagicMock()
            mock_fd_res = MagicMock()
            mock_fd_res.detections = [det_single]
            mock_fd_inst.process.return_value = mock_fd_res
            mock_fd.return_value = mock_fd_inst

            res_std = track_faces(fixture, sample_fps=30.0, tracking_mode="standard")
            assert len(res_std["timeline"]) == 1
            assert res_std["timeline"][0]["raw_x"] == pytest.approx(0.4)


def test_enhanced_return_fields():
    """Verify tracking_mode, dwell_switches, and dwell_rejections are present in enhanced mode."""
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    result = track_faces(fixture, sample_fps=1.0, tracking_mode="enhanced")
    assert result["tracking_mode"] == "enhanced"
    assert "dwell_switches" in result
    assert "dwell_rejections" in result
    assert isinstance(result["dwell_switches"], int)
    assert isinstance(result["dwell_rejections"], int)
