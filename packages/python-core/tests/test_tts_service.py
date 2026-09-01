from pathlib import Path
from clipforge_core.services.tts_service import VOICE_PERSONAS, synthesize_voiceover


def test_voice_personas_catalog():
    assert len(VOICE_PERSONAS) >= 4
    ids = [v["id"] for v in VOICE_PERSONAS]
    assert "en-US-JennyNeural" in ids
    assert "en-GB-SoniaNeural" in ids


def test_synthesize_voiceover_empty():
    res = synthesize_voiceover("", voice_id="en-US-JennyNeural")
    assert res["status"] in ("empty_fallback", "fallback_generated", "success")


def test_synthesize_voiceover_audio_file(tmp_path):
    out_mp3 = tmp_path / "test_vo.mp3"
    res = synthesize_voiceover(
        text="Welcome to ClipForge AI voiceover studio.",
        voice_id="en-US-JennyNeural",
        output_path=out_mp3,
    )
    assert out_mp3.exists()
    assert out_mp3.stat().st_size > 500
