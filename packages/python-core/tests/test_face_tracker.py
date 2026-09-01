from pathlib import Path

from clipforge_core.services.face_tracker import track_faces

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_track_faces_on_fixture_with_graceful_fallback():
    # Our synthetic testsrc video contains no human faces, so it must gracefully fallback to center-crop
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    result = track_faces(fixture, sample_fps=2.0)
    assert "timeline" in result
    assert "average_focal_x" in result
    assert result["fallback_used"] is True  # Verified graceful fallback!
    assert 0.4 <= result["average_focal_x"] <= 0.6
