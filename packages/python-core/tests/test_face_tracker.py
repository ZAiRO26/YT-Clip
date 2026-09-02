from pathlib import Path

from clipforge_core.services.face_tracker import track_faces

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_track_faces_on_fixture_with_graceful_fallback():
    # Synthetic testsrc video contains no human faces, so it must gracefully fallback to center-crop
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    result = track_faces(fixture, sample_fps=2.0)
    assert "timeline" in result
    assert "average_focal_x" in result
    assert "std_dev_focal_x" in result
    assert result["fallback_used"] is True  # Verified graceful fallback!
    assert 0.4 <= result["average_focal_x"] <= 0.6


def test_track_faces_on_spoken_human_fixture():
    spoken_fixture = FIXTURES_DIR / "authorized-spoken" / "spoken_video.mp4"
    if spoken_fixture.exists():
        result = track_faces(spoken_fixture, sample_fps=3.0)
        assert result["fallback_used"] is False
        assert result["detection_rate"] > 0.80
        assert result["faces_detected_samples"] > 0
        assert result["std_dev_focal_x"] > 0.05  # Confirms real dynamic variance across frames

