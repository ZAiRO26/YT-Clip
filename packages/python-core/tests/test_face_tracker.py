"""
Tests for ClipForge AI Face Tracker with Active Speaker Detection.

Tests verify:
1. Backward compatibility (no transcript → works like before)
2. Center-crop fallback for synthetic videos without human faces
3. Active speaker tracking with transcript data
4. Speech interval builder logic
5. Output contract stability (all required keys present)
"""
from pathlib import Path
from unittest.mock import patch

from clipforge_core.services.face_tracker import (
    _build_speech_intervals,
    _is_speech_active,
    track_faces,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# --- Backward Compatibility Tests ---

def test_track_faces_on_fixture_with_graceful_fallback():
    """Synthetic testsrc video contains no human faces, so it must gracefully fallback to center-crop."""
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    result = track_faces(fixture, sample_fps=2.0)
    assert "timeline" in result
    assert "average_focal_x" in result
    assert "std_dev_focal_x" in result
    assert result["fallback_used"] is True  # Verified graceful fallback!
    assert 0.4 <= result["average_focal_x"] <= 0.6


def test_track_faces_backward_compat_no_transcript():
    """Calling track_faces without transcript arg should work identically to v1."""
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    result = track_faces(fixture, sample_fps=2.0)
    # Output contract: all v1 keys present
    assert "timeline" in result
    assert "average_focal_x" in result
    assert "std_dev_focal_x" in result
    assert "detection_rate" in result
    assert "fallback_used" in result
    assert "total_samples" in result
    assert "faces_detected_samples" in result
    # New keys are present but should not affect behavior
    assert "speaker_tracking_used" in result
    assert result["speaker_tracking_used"] is False  # No transcript → no speaker tracking


def test_track_faces_on_spoken_human_fixture():
    spoken_fixture = FIXTURES_DIR / "authorized-spoken" / "spoken_video.mp4"
    if spoken_fixture.exists():
        result = track_faces(spoken_fixture, sample_fps=3.0)
        assert result["fallback_used"] is False
        assert result["detection_rate"] > 0.80
        assert result["faces_detected_samples"] > 0
        assert result["std_dev_focal_x"] > 0.05  # Confirms real dynamic variance across frames


# --- Speech Interval Tests ---

def test_build_speech_intervals_empty():
    """No transcript yields no speech intervals."""
    assert _build_speech_intervals(None) == []
    assert _build_speech_intervals({}) == []
    assert _build_speech_intervals({"segments": []}) == []


def test_build_speech_intervals_basic():
    """Non-overlapping segments are preserved."""
    transcript = {
        "segments": [
            {"start": 1.0, "end": 3.0, "text": "hello"},
            {"start": 5.0, "end": 7.0, "text": "world"},
        ]
    }
    intervals = _build_speech_intervals(transcript)
    assert intervals == [(1.0, 3.0), (5.0, 7.0)]


def test_build_speech_intervals_merges_adjacent():
    """Segments within 0.3s merge into one interval."""
    transcript = {
        "segments": [
            {"start": 1.0, "end": 3.0, "text": "hello"},
            {"start": 3.2, "end": 5.0, "text": "world"},
        ]
    }
    intervals = _build_speech_intervals(transcript)
    assert intervals == [(1.0, 5.0)]


def test_build_speech_intervals_gap_preserved():
    """Segments with >0.3s gap remain separate."""
    transcript = {
        "segments": [
            {"start": 1.0, "end": 3.0, "text": "hello"},
            {"start": 4.0, "end": 6.0, "text": "world"},
        ]
    }
    intervals = _build_speech_intervals(transcript)
    assert len(intervals) == 2


def test_is_speech_active_basic():
    """Binary search correctly identifies speech vs silence timestamps."""
    intervals = [(1.0, 3.0), (5.0, 7.0), (10.0, 12.0)]

    assert _is_speech_active(0.5, intervals) is False
    assert _is_speech_active(1.0, intervals) is True
    assert _is_speech_active(2.0, intervals) is True
    assert _is_speech_active(3.0, intervals) is True
    assert _is_speech_active(4.0, intervals) is False
    assert _is_speech_active(5.5, intervals) is True
    assert _is_speech_active(8.0, intervals) is False
    assert _is_speech_active(11.0, intervals) is True
    assert _is_speech_active(15.0, intervals) is False


def test_is_speech_active_empty():
    """Empty intervals always return False."""
    assert _is_speech_active(5.0, []) is False


# --- Output Contract Test ---

def test_output_contract_keys():
    """Verify all expected output keys are present regardless of input."""
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    result = track_faces(fixture, sample_fps=1.0)

    required_keys = {
        "timeline", "average_focal_x", "std_dev_focal_x",
        "total_samples", "faces_detected_samples", "detection_rate",
        "fallback_used", "speaker_tracking_used",
    }
    assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"

    # Each timeline entry has required fields
    for entry in result.get("timeline", []):
        assert "time_sec" in entry
        assert "focal_x" in entry
        assert "raw_x" in entry
        assert "face_detected" in entry


def test_speaker_tracking_with_transcript_on_synthetic():
    """Passing a transcript to a synthetic (no-face) video should still work gracefully."""
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    fake_transcript = {
        "segments": [
            {"start": 0.0, "end": 2.0, "text": "Testing speaker detection"},
            {"start": 3.0, "end": 5.0, "text": "on a synthetic video"},
        ]
    }

    result = track_faces(fixture, sample_fps=1.0, transcript=fake_transcript)
    # Should still fallback because no real faces exist in synthetic video
    assert result["fallback_used"] is True
    # Speaker tracking had no faces to work with
    assert result["speaker_tracking_used"] is False
    assert 0.4 <= result["average_focal_x"] <= 0.6
