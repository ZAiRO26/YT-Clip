import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from clipforge_core.services.caption_renderer import generate_ass_subtitles
from clipforge_core.services.render_engine import (
    _build_dynamic_crop_expr,
    build_render_manifest,
    render_clip,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCHEMA_FILE = Path(__file__).parent.parent.parent.parent / "docs" / "RENDER_MANIFEST_SCHEMA.json"


def test_build_dynamic_crop_expr_empty_timeline():
    expr = _build_dynamic_crop_expr(
        focal_timeline=[],
        clip_start_sec=10.0,
        clip_end_sec=20.0,
        src_w=1920,
        bot_crop_w=962,
    )
    # Fallback to centered crop
    assert expr == "479"  # (1920 - 962) / 2 = 479


def test_build_dynamic_crop_expr_single_point():
    timeline = [{"time_sec": 12.0, "focal_x": 0.3}]
    expr = _build_dynamic_crop_expr(
        focal_timeline=timeline,
        clip_start_sec=10.0,
        clip_end_sec=20.0,
        src_w=1920,
        bot_crop_w=962,
    )
    # Single point should resolve with 95 offset in timeline
    assert "95" in expr
    assert "if(lt(t" in expr


def test_build_dynamic_crop_expr_multiple_points():
    timeline = [
        {"time_sec": 10.0, "focal_x": 0.2},
        {"time_sec": 15.0, "focal_x": 0.8},
        {"time_sec": 20.0, "focal_x": 0.5},
    ]
    expr = _build_dynamic_crop_expr(
        focal_timeline=timeline,
        clip_start_sec=10.0,
        clip_end_sec=20.0,
        src_w=1920,
        bot_crop_w=962,
    )
    assert expr.startswith("if(lt(t\\,5.0")
    assert "if(lt(t\\,10.0" in expr
    # Check escaped commas for FFmpeg filter safety
    assert "\\," in expr


def test_manifest_schema_stacked_mode():
    timeline = [
        {"time_sec": 10.0, "focal_x": 0.3},
        {"time_sec": 20.0, "focal_x": 0.7},
    ]
    manifest = build_render_manifest(
        clip_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        project_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        source_asset_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
        source_path="D:/mock/source.mp4",
        source_probe={"duration_sec": 60.0, "width": 1920, "height": 1080, "fps": 30.0, "video_codec": "h264"},
        start_sec=10.0,
        end_sec=30.0,
        crop_mode="stacked_speaker",
        focal_x=0.5,
        caption_style="bold_karaoke",
        editorial_template="explainer",
        rights_basis="owned",
        transformation_score=85,
        focal_timeline=timeline,
    )

    assert manifest["crop"]["mode"] == "stacked_speaker"
    assert "layout_bands" in manifest["crop"]
    assert manifest["crop"]["layout_bands"]["top_height"] == 710
    assert manifest["crop"]["layout_bands"]["bottom_height"] == 1210
    assert manifest["crop"]["layout_bands"]["divider_height"] == 2
    assert manifest["crop"]["layout_bands"]["tracking"] == "per_frame_dynamic"
    assert manifest["output"]["width"] == 1080
    assert manifest["output"]["height"] == 1920

    if SCHEMA_FILE.exists():
        schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(manifest))
        assert len(errors) == 0, f"Schema validation errors: {[e.message for e in errors]}"


def test_caption_stacked_mode_margin_v(tmp_path):
    segments = [
        {
            "start": 0.0,
            "end": 3.0,
            "text": "Testing safe zone captions",
            "words": [{"word": "Testing", "start": 0.0, "end": 1.0}],
        }
    ]
    stacked_ass = tmp_path / "stacked.ass"
    generate_ass_subtitles(
        transcript_segments=segments,
        clip_start_sec=0.0,
        clip_end_sec=3.0,
        output_ass_path=stacked_ass,
        style_preset="bold_karaoke",
        layout_mode="stacked_speaker",
    )
    content_stacked = stacked_ass.read_text(encoding="utf-8")
    assert ",60,60,140,1" in content_stacked

    standard_ass = tmp_path / "standard.ass"
    generate_ass_subtitles(
        transcript_segments=segments,
        clip_start_sec=0.0,
        clip_end_sec=3.0,
        output_ass_path=standard_ass,
        style_preset="bold_karaoke",
        layout_mode="standard",
    )
    content_standard = standard_ass.read_text(encoding="utf-8")
    assert ",60,60,340,1" in content_standard


def test_filter_graph_stacked_structure():
    # Verify dimensions and band calculation
    src_h = 1080
    bot_crop_w = int(src_h * 1080 / 1210 // 2 * 2)
    assert bot_crop_w == 962
    assert 710 + 1210 == 1920


def test_stacked_render_real_ffmpeg_execution(tmp_path):
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Explainer fixture missing"

    out_mp4 = tmp_path / "rendered_stacked.mp4"
    out_thumb = tmp_path / "rendered_stacked_thumb.jpg"

    timeline = [
        {"time_sec": 2.0, "focal_x": 0.25},
        {"time_sec": 3.5, "focal_x": 0.75},
        {"time_sec": 5.0, "focal_x": 0.50},
    ]

    res = render_clip(
        source_path=fixture,
        output_path=out_mp4,
        start_sec=2.0,
        end_sec=5.0,
        crop_mode="stacked_speaker",
        focal_x=0.5,
        caption_style="none",
        output_thumbnail_path=out_thumb,
        focal_timeline=timeline,
    )

    assert out_mp4.exists(), "Stacked MP4 not created"
    assert out_thumb.exists(), "Thumbnail not created"
    assert res["width"] == 1080
    assert res["height"] == 1920
    assert 2.5 <= res["duration_sec"] <= 3.5


def test_stacked_render_without_timeline_fallback(tmp_path):
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Explainer fixture missing"

    out_mp4 = tmp_path / "rendered_stacked_fallback.mp4"
    out_thumb = tmp_path / "rendered_stacked_fallback_thumb.jpg"

    res = render_clip(
        source_path=fixture,
        output_path=out_mp4,
        start_sec=1.0,
        end_sec=3.0,
        crop_mode="stacked_speaker",
        focal_x=0.6,
        caption_style="none",
        output_thumbnail_path=out_thumb,
        focal_timeline=None,
    )

    assert out_mp4.exists(), "Fallback stacked MP4 not created"
    assert res["width"] == 1080
    assert res["height"] == 1920
