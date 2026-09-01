from clipforge_core.schemas import BrandKitCreate, ClipRerenderRequest


def test_brand_kit_create_schema():
    payload = {
        "name": "Acme Media Studio",
        "primary_color": "#6366F1",
        "secondary_color": "#10B981",
        "font_family": "Montserrat",
        "watermark_position": "top_right",
        "default_cta_text": "Follow for daily clips",
    }
    schema = BrandKitCreate(**payload)
    assert schema.name == "Acme Media Studio"
    assert schema.primary_color == "#6366F1"


def test_clip_rerender_request_schema():
    payload = {
        "start_sec": 12.0,
        "end_sec": 42.5,
        "caption_style": "minimal",
        "crop_mode": "blur_background",
        "voice_id": "en-US-JennyNeural",
        "voiceover_text": "Here is original commentary.",
        "music_track": "ambient_focus",
        "effects": [{"id": "vignette", "intensity": 0.5}],
    }
    req = ClipRerenderRequest(**payload)
    assert req.start_sec == 12.0
    assert req.crop_mode == "blur_background"
    assert len(req.effects) == 1
