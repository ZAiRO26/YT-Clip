from pathlib import Path

from clipforge_core.services.render_engine import build_render_manifest, render_clip

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_build_render_manifest():
    manifest = build_render_manifest(
        clip_id="11111111-1111-1111-1111-111111111111",
        project_id="22222222-2222-2222-2222-222222222222",
        source_asset_id="33333333-3333-3333-3333-333333333333",
        source_path="D:/mock/source.mp4",
        source_probe={"duration_sec": 60.0, "width": 1920, "height": 1080, "fps": 30.0, "video_codec": "h264"},
        start_sec=10.0,
        end_sec=30.0,
        crop_mode="face_track",
        focal_x=0.5,
        caption_style="bold_karaoke",
        editorial_template="explainer",
        rights_basis="owned",
        transformation_score=85,
        transformation_breakdown={"source_exclusivity": 20, "commentary_depth": 25},
    )

    assert manifest["manifest_version"] == "1.0.0"
    assert manifest["output"]["width"] == 1080
    assert manifest["output"]["height"] == 1920
    assert manifest["metadata"]["transformation_score"] == 85
    assert manifest["crop"]["mode"] == "face_track"

    # Programmatic Draft-07 schema validation in unit test
    import json
    from jsonschema import Draft7Validator
    schema_file = Path(__file__).parent.parent.parent.parent / "docs" / "RENDER_MANIFEST_SCHEMA.json"
    if schema_file.exists():
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(manifest))
        assert len(errors) == 0, f"Schema validation failed: {[e.message for e in errors]}"


def test_render_clip_real_ffmpeg_execution(tmp_path):
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_mp4 = tmp_path / "rendered_vertical.mp4"
    out_thumb = tmp_path / "rendered_thumb.jpg"

    res = render_clip(
        source_path=fixture,
        output_path=out_mp4,
        start_sec=2.0,
        end_sec=6.0,  # 4 second test render
        crop_mode="face_track",
        focal_x=0.5,
        caption_style="none",
        output_thumbnail_path=out_thumb,
    )

    assert out_mp4.exists(), "Rendered MP4 not created"
    assert out_thumb.exists(), "Thumbnail not created"
    assert res["width"] == 1080
    assert res["height"] == 1920
    assert 3.5 <= res["duration_sec"] <= 4.5
