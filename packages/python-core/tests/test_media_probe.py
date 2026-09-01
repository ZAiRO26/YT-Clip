from pathlib import Path

import pytest
from clipforge_core.services.media_probe import probe_media

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_probe_explainer_1080p():
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    probe = probe_media(fixture)
    assert probe["width"] == 1920
    assert probe["height"] == 1080
    assert probe["fps"] == 30.0
    assert probe["video_codec"] == "h264"
    assert probe["has_audio"] is True
    assert probe["is_vertical"] is False
    assert 24.5 <= probe["duration_sec"] <= 25.5


def test_probe_vertical_720p():
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    probe = probe_media(fixture)
    assert probe["width"] == 720
    assert probe["height"] == 1280
    assert probe["fps"] == 30.0
    assert probe["is_vertical"] is True
    assert 14.5 <= probe["duration_sec"] <= 15.5


def test_probe_commentary_24fps():
    fixture = FIXTURES_DIR / "authorized_commentary_short.mp4"
    assert fixture.exists(), "Fixture missing"

    probe = probe_media(fixture)
    assert probe["width"] == 1280
    assert probe["height"] == 720
    assert probe["fps"] == 24.0
    assert 19.5 <= probe["duration_sec"] <= 20.5


def test_probe_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        probe_media("nonexistent_video.mp4")
