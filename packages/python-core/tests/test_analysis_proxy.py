from pathlib import Path

from clipforge_core.services.analysis_proxy import PROXY_HEIGHT, create_analysis_proxy
from clipforge_core.services.media_probe import probe_media

FIXTURES = Path(__file__).parent / "fixtures"


def test_proxy_is_small_and_spans_same_timeline(tmp_path):
    source = FIXTURES / "authorized-spoken" / "spoken_video.mp4"  # 1080p
    proxy = create_analysis_proxy(source, tmp_path / "analysis_proxy.mp4")

    assert proxy is not None and proxy.exists()
    src_probe, proxy_probe = probe_media(source), probe_media(proxy)
    assert proxy_probe["height"] == PROXY_HEIGHT
    assert abs(proxy_probe["duration_sec"] - src_probe["duration_sec"]) <= 0.5
    assert abs(proxy_probe["fps"] - src_probe["fps"]) < 0.01


def test_proxy_skipped_for_already_small_source(tmp_path):
    source = FIXTURES / "authorized-spoken" / "spoken_video.mp4"
    small = create_analysis_proxy(source, tmp_path / "small.mp4")
    assert small is not None
    # A 540p input needs no proxy: callers analyse it directly
    assert create_analysis_proxy(small, tmp_path / "again.mp4") is None


def test_proxy_failure_falls_back_to_none(tmp_path):
    assert create_analysis_proxy(tmp_path / "missing.mp4", tmp_path / "out.mp4") is None
