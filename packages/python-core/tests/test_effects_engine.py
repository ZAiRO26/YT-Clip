import subprocess
from pathlib import Path

from clipforge_core.services.effects_engine import (
    EFFECT_CATALOG,
    apply_motion_effects,
    build_effect_filter,
)
from clipforge_core.services.media_probe import probe_media

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_effect_catalog():
    assert len(EFFECT_CATALOG) >= 6
    ids = [e["id"] for e in EFFECT_CATALOG]
    assert "film_grain" in ids
    assert "vignette" in ids


def test_build_effect_filter():
    grain = build_effect_filter("film_grain", intensity=0.4, start_sec=0.0, end_sec=5.0)
    assert "noise=" in grain
    assert "between(t,0.0,5.0)" in grain

    vignette = build_effect_filter("vignette", intensity=0.5)
    assert "vignette=" in vignette

    # Test Zoom filter duration calculation
    zoom = build_effect_filter("zoom", intensity=0.5, duration_sec=39.3)
    assert "scale='trunc(in_w*(1+" in zoom
    assert "0.001527" in zoom
    assert "crop=in_w:in_h:(iw-in_w)/2:(ih-in_h)/2" in zoom

    # Test Camera Shake filter bounded jitter
    shake = build_effect_filter("camera_shake", intensity=0.5)
    assert "crop=in_w-12:in_h-12:" in shake
    assert "scale=in_w:in_h:flags=lanczos" in shake

    # Test RGB Glitch with unshifted green channel and edge smear
    rgb = build_effect_filter("rgb_split", intensity=0.5)
    assert "rgbashift=rh=3:bh=-3:edge=smear" in rgb
    assert "gh=" not in rgb
    assert "gv=" not in rgb

    # Test VHS Retro color grading and scanlines
    vhs = build_effect_filter("vhs_noise", intensity=0.5)
    assert "eq=saturation=1.12:contrast=1.06" in vhs
    assert "noise=alls=9:allf=t+u" in vhs


def _verify_ffmpeg_decode(file_path: Path):
    cmd = ["ffmpeg", "-v", "error", "-i", str(file_path), "-f", "null", "-"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"FFmpeg decode failed on {file_path}: {res.stderr}"


def test_apply_film_grain_individually(tmp_path):
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_fx = tmp_path / "grain_output.mp4"
    res = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_fx,
        effects=[{"id": "film_grain", "intensity": 0.35}],
    )

    assert out_fx.exists()
    assert res["applied_effects"] == ["film_grain"]
    _verify_ffmpeg_decode(out_fx)

    probe = probe_media(out_fx)
    assert probe["video_codec"] == "h264"
    assert probe["width"] == 720
    assert probe["height"] == 1280


def test_apply_vignette_individually(tmp_path):
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_fx = tmp_path / "vignette_output.mp4"
    res = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_fx,
        effects=[{"id": "vignette", "intensity": 0.5}],
    )

    assert out_fx.exists()
    assert res["applied_effects"] == ["vignette"]
    _verify_ffmpeg_decode(out_fx)

    probe = probe_media(out_fx)
    assert probe["video_codec"] == "h264"
    assert probe["width"] == 720
    assert probe["height"] == 1280


def test_apply_zoom_individually(tmp_path):
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_fx = tmp_path / "zoom_output.mp4"
    res = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_fx,
        effects=[{"id": "zoom", "intensity": 0.5}],
        duration_sec=3.0,
    )

    assert out_fx.exists()
    assert res["applied_effects"] == ["zoom"]
    _verify_ffmpeg_decode(out_fx)

    probe = probe_media(out_fx)
    assert probe["video_codec"] == "h264"


def test_apply_camera_shake_individually(tmp_path):
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_fx = tmp_path / "shake_output.mp4"
    res = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_fx,
        effects=[{"id": "camera_shake", "intensity": 0.5}],
        duration_sec=3.0,
    )

    assert out_fx.exists()
    assert res["applied_effects"] == ["camera_shake"]
    _verify_ffmpeg_decode(out_fx)


def test_extreme_intensity_boundary(tmp_path):
    """Test boundary condition at intensity=1.0 (maximum) to ensure no out-of-bounds crop."""
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_fx = tmp_path / "extreme_boundary_output.mp4"
    res = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_fx,
        effects=[
            {"id": "zoom", "intensity": 1.0},
            {"id": "camera_shake", "intensity": 1.0},
            {"id": "film_grain", "intensity": 1.0},
            {"id": "vignette", "intensity": 1.0},
        ],
        duration_sec=3.0,
    )

    assert out_fx.exists()
    assert len(res["applied_effects"]) == 4
    _verify_ffmpeg_decode(out_fx)


def test_apply_all_four_effects_combined(tmp_path):
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_fx = tmp_path / "combined_output.mp4"
    res = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_fx,
        effects=[
            {"id": "zoom", "intensity": 0.5},
            {"id": "camera_shake", "intensity": 0.4},
            {"id": "film_grain", "intensity": 0.3},
            {"id": "vignette", "intensity": 0.5},
        ],
        duration_sec=3.0,
    )

    assert out_fx.exists()
    assert len(res["applied_effects"]) == 4
    _verify_ffmpeg_decode(out_fx)


def test_apply_rgb_split_individually(tmp_path):
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    # Moderate intensity (0.5)
    out_mod = tmp_path / "rgb_split_mod.mp4"
    res_mod = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_mod,
        effects=[{"id": "rgb_split", "intensity": 0.5}],
    )
    assert out_mod.exists()
    assert res_mod["applied_effects"] == ["rgb_split"]
    _verify_ffmpeg_decode(out_mod)

    # Max intensity boundary (1.0)
    out_max = tmp_path / "rgb_split_max.mp4"
    res_max = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_max,
        effects=[{"id": "rgb_split", "intensity": 1.0}],
    )
    assert out_max.exists()
    _verify_ffmpeg_decode(out_max)


def test_apply_vhs_noise_individually(tmp_path):
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    # Moderate intensity (0.5)
    out_mod = tmp_path / "vhs_mod.mp4"
    res_mod = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_mod,
        effects=[{"id": "vhs_noise", "intensity": 0.5}],
    )
    assert out_mod.exists()
    assert res_mod["applied_effects"] == ["vhs_noise"]
    _verify_ffmpeg_decode(out_mod)

    # Max intensity boundary (1.0)
    out_max = tmp_path / "vhs_max.mp4"
    res_max = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_max,
        effects=[{"id": "vhs_noise", "intensity": 1.0}],
    )
    assert out_max.exists()
    _verify_ffmpeg_decode(out_max)


def test_apply_all_six_effects_stacked(tmp_path):
    """Test full 6-effect stack in a single filter pass."""
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_fx = tmp_path / "all_six_output.mp4"
    res = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_fx,
        effects=[
            {"id": "film_grain", "intensity": 0.3},
            {"id": "vignette", "intensity": 0.4},
            {"id": "zoom", "intensity": 0.5},
            {"id": "camera_shake", "intensity": 0.3},
            {"id": "rgb_split", "intensity": 0.4},
            {"id": "vhs_noise", "intensity": 0.3},
        ],
        duration_sec=3.0,
    )

    assert out_fx.exists()
    assert len(res["applied_effects"]) == 6
    _verify_ffmpeg_decode(out_fx)


def test_apply_no_effects_regression(tmp_path):
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_fx = tmp_path / "no_fx_output.mp4"
    res = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_fx,
        effects=[],
    )

    assert out_fx.exists()
    assert res["applied_effects"] == []
    _verify_ffmpeg_decode(out_fx)

