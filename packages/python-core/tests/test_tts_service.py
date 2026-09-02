from pathlib import Path
from clipforge_core.services.tts_service import (
    VOICE_PERSONAS,
    LEGACY_VOICE_ALIASES,
    resolve_voice_id,
    synthesize_voiceover,
)


def test_voice_personas_catalog():
    assert len(VOICE_PERSONAS) >= 5
    ids = [v["id"] for v in VOICE_PERSONAS]
    assert "af_bella" in ids
    assert "am_adam" in ids
    assert "bf_emma" in ids
    assert "bm_george" in ids
    assert "af_sarah" in ids


def test_resolve_voice_id_aliases():
    assert resolve_voice_id("en-US-JennyNeural") == "af_bella"
    assert resolve_voice_id("en-GB-RyanNeural") == "bm_george"
    assert resolve_voice_id("en-US-GuyNeural") == "am_adam"
    assert resolve_voice_id("bella") == "af_bella"
    assert resolve_voice_id("unknown_voice_id") == "af_bella"


def test_synthesize_voiceover_empty(tmp_path):
    out_wav = tmp_path / "empty_vo.wav"
    res = synthesize_voiceover("", voice_id="af_bella", output_path=out_wav)
    assert res["status"] in ("empty_fallback", "fallback_generated", "success")
    assert out_wav.exists()


def test_synthesize_voiceover_kokoro_local(tmp_path):
    out_wav = tmp_path / "test_bella.wav"
    res = synthesize_voiceover(
        text="Welcome to ClipForge Audio Studio with local Kokoro narration.",
        voice_id="af_bella",
        output_path=out_wav,
    )
    assert res["status"] == "success"
    assert res["voice_id"] == "af_bella"
    assert res["duration_sec"] > 1.0
    assert out_wav.exists()
    assert out_wav.stat().st_size > 5000


def test_synthesize_voiceover_british_voice(tmp_path):
    out_wav = tmp_path / "test_george.wav"
    res = synthesize_voiceover(
        text="Analyzing historical patterns across modern European development.",
        voice_id="bm_george",
        output_path=out_wav,
    )
    assert res["status"] == "success"
    assert res["voice_id"] == "bm_george"
    assert res["duration_sec"] > 1.0
    assert out_wav.exists()
