from pathlib import Path

from clipforge_core.services.scene_detector import detect_scenes

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_detect_scenes_on_fixture():
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    scenes = detect_scenes(fixture)
    assert len(scenes) >= 1
    first = scenes[0]
    assert "start_sec" in first
    assert "end_sec" in first
    assert "duration_sec" in first
    assert first["duration_sec"] > 0
