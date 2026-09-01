from pathlib import Path
from clipforge_core.services.caption_renderer import generate_ass_subtitles

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_generate_ass_bold_karaoke(tmp_path):
    segments = [
        {
            "start": 0.0,
            "end": 4.5,
            "text": "Welcome to ClipForge AI studio",
            "words": [
                {"word": "Welcome", "start": 0.1, "end": 0.8},
                {"word": "to", "start": 0.9, "end": 1.1},
                {"word": "ClipForge", "start": 1.2, "end": 2.0},
                {"word": "AI", "start": 2.1, "end": 2.6},
                {"word": "studio", "start": 2.7, "end": 3.8},
            ],
        }
    ]

    out_ass = tmp_path / "test_karaoke.ass"
    generate_ass_subtitles(
        transcript_segments=segments,
        clip_start_sec=0.0,
        clip_end_sec=5.0,
        output_ass_path=out_ass,
        style_preset="bold_karaoke",
    )

    assert out_ass.exists()
    content = out_ass.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "{\\k" in content  # Contains karaoke tags!
    assert "CLIPFORGE" in content


def test_generate_ass_none_preset(tmp_path):
    out_ass = tmp_path / "test_none.ass"
    generate_ass_subtitles(
        transcript_segments=[],
        clip_start_sec=0.0,
        clip_end_sec=5.0,
        output_ass_path=out_ass,
        style_preset="none",
    )
    assert out_ass.exists()
    content = out_ass.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "Dialogue:" not in content
