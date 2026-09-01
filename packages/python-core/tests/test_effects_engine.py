from pathlib import Path
from clipforge_core.services.effects_engine import (
    EFFECT_CATALOG,
    apply_motion_effects,
    build_effect_filter,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_effect_catalog():
    assert len(EFFECT_CATALOG) >= 6
    ids = [e["id"] for e in EFFECT_CATALOG]
    assert "zoom" in ids
    assert "camera_shake" in ids
    assert "film_grain" in ids
    assert "vignette" in ids


def test_build_effect_filter():
    grain = build_effect_filter("film_grain", intensity=0.4, start_sec=0.0, end_sec=5.0)
    assert "noise=" in grain
    assert "between(t,0.0,5.0)" in grain

    vignette = build_effect_filter("vignette", intensity=0.5)
    assert "vignette=" in vignette

    shake = build_effect_filter("camera_shake", intensity=0.5)
    assert "crop=" in shake


def test_apply_motion_effects_live_ffmpeg(tmp_path):
    fixture = FIXTURES_DIR / "authorized_vertical_720p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_fx = tmp_path / "effect_output.mp4"
    effects = [
        {"id": "vignette", "intensity": 0.5},
        {"id": "film_grain", "intensity": 0.3},
    ]

    res = apply_motion_effects(
        source_video_path=fixture,
        output_video_path=out_fx,
        effects=effects,
    )

    assert out_fx.exists(), "Effect video was not rendered"
    assert out_fx.stat().st_size > 1000
    assert len(res["applied_effects"]) == 2
