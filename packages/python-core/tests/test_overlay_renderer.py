from clipforge_core.services.overlay_renderer import (
    create_cta_end_card,
    create_hook_card,
    create_lower_third,
)


def test_create_hook_card(tmp_path):
    out_png = tmp_path / "hook_card.png"
    create_hook_card(
        title="Why autonomous AI models are changing software development",
        hook_type="bold_statement",
        output_png_path=out_png,
    )
    assert out_png.exists()
    assert out_png.stat().st_size > 1000


def test_create_lower_third(tmp_path):
    out_png = tmp_path / "lower_third.png"
    create_lower_third(
        attribution_text="Dr. Andrew Ng — Founder, DeepLearning.AI",
        context_tag="Source Citation",
        output_png_path=out_png,
    )
    assert out_png.exists()
    assert out_png.stat().st_size > 1000


def test_create_cta_end_card(tmp_path):
    out_png = tmp_path / "cta_card.png"
    create_cta_end_card(
        takeaway_text="Emphasize original human commentary for sustainable channels.",
        cta_action="Subscribe for full breakdowns",
        output_png_path=out_png,
    )
    assert out_png.exists()
    assert out_png.stat().st_size > 1000
