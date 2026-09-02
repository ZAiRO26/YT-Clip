"""
ClipForge AI — Voiceover TTS Synthesis Engine (v2)
Local Apache-2.0 Kokoro TTS adapter running 100% offline via ONNX Runtime CPU provider.

Voice Personas:
- af_bella (Bella — Warm & Engaging Explainer, American Female)
- am_adam (Adam — Dynamic & Authoritative Host, American Male)
- bf_emma (Emma — Thoughtful News & Commentary, British Female)
- bm_george (George — Documentary & Storyteller, British Male)
- af_sarah (Sarah — Clear & Polished Narrator, American Female)
- am_michael (Michael — Casual Conversation & Podcast, American Male)
- af_nicole (Nicole — Relaxed & Natural Dialogue, American Female)
"""
import logging
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import soundfile as sf

logger = logging.getLogger(__name__)

VOICE_PERSONAS: List[Dict[str, str]] = [
    {
        "id": "af_bella",
        "name": "Bella",
        "description": "Warm & Engaging Explainer",
        "accent": "American",
        "gender": "Female",
    },
    {
        "id": "am_adam",
        "name": "Adam",
        "description": "Dynamic & Authoritative Host",
        "accent": "American",
        "gender": "Male",
    },
    {
        "id": "bf_emma",
        "name": "Emma",
        "description": "Thoughtful News & Commentary",
        "accent": "British",
        "gender": "Female",
    },
    {
        "id": "bm_george",
        "name": "George",
        "description": "Documentary & Storyteller",
        "accent": "British",
        "gender": "Male",
    },
    {
        "id": "af_sarah",
        "name": "Sarah",
        "description": "Clear & Polished Narrator",
        "accent": "American",
        "gender": "Female",
    },
    {
        "id": "am_michael",
        "name": "Michael",
        "description": "Conversational & Podcast Host",
        "accent": "American",
        "gender": "Male",
    },
    {
        "id": "af_nicole",
        "name": "Nicole",
        "description": "Relaxed & Natural Dialogue",
        "accent": "American",
        "gender": "Female",
    },
]

# Legacy Edge-TTS mapping aliases for full backward compatibility
LEGACY_VOICE_ALIASES: Dict[str, str] = {
    "en-US-JennyNeural": "af_bella",
    "en-US-GuyNeural": "am_adam",
    "en-GB-SoniaNeural": "bf_emma",
    "en-GB-RyanNeural": "bm_george",
    "en-US-AriaNeural": "af_sarah",
    "bella": "af_bella",
    "adam": "am_adam",
    "emma": "bf_emma",
    "george": "bm_george",
    "sarah": "af_sarah",
    "michael": "am_michael",
    "nicole": "af_nicole",
}

_KOKORO_LOCK = threading.Lock()
_KOKORO_INSTANCE: Optional[Any] = None


def _get_model_paths() -> tuple[Path, Path]:
    """Resolve model and voices binary file paths."""
    curr = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = curr / "models" / "kokoro"
        if candidate.exists() and (candidate / "kokoro-v0_19.onnx").exists():
            return candidate / "kokoro-v0_19.onnx", candidate / "voices.bin"
        if (curr / "pyproject.toml").exists() and (curr / "packages").exists():
            candidate = curr / "models" / "kokoro"
            return candidate / "kokoro-v0_19.onnx", candidate / "voices.bin"
        curr = curr.parent

    project_root = Path(__file__).resolve().parents[4]
    models_dir = project_root / "models" / "kokoro"
    return models_dir / "kokoro-v0_19.onnx", models_dir / "voices.bin"


def get_kokoro_engine() -> Any:
    """Thread-safe lazy singleton loader for Kokoro ONNX model."""
    global _KOKORO_INSTANCE
    if _KOKORO_INSTANCE is not None:
        return _KOKORO_INSTANCE

    with _KOKORO_LOCK:
        if _KOKORO_INSTANCE is not None:
            return _KOKORO_INSTANCE

        model_path, voices_path = _get_model_paths()
        if not model_path.exists() or not voices_path.exists():
            # Trigger setup verification script if not present
            try:
                from scripts.download_kokoro_models import ensure_kokoro_models
                ensure_kokoro_models()
            except Exception as e:
                logger.error(f"[Kokoro] Failed to auto-download models: {e}")
                raise RuntimeError(
                    f"Kokoro model files missing at {model_path}. "
                    "Run 'python scripts/download_kokoro_models.py' to download model assets."
                ) from e

        from kokoro_onnx import Kokoro
        logger.info(f"[Kokoro] Initializing local ONNX model from {model_path} (Zero Network inference)")
        _KOKORO_INSTANCE = Kokoro(str(model_path), str(voices_path))
        return _KOKORO_INSTANCE


def resolve_voice_id(voice_id: str) -> str:
    """Normalize and resolve voice ID to a supported Kokoro voice."""
    if voice_id in LEGACY_VOICE_ALIASES:
        return LEGACY_VOICE_ALIASES[voice_id]
    valid_voices = {v["id"] for v in VOICE_PERSONAS}
    if voice_id in valid_voices:
        return voice_id
    # Default fallback to af_bella
    logger.warning(f"[Kokoro] Unknown voice ID '{voice_id}', falling back to 'af_bella'")
    return "af_bella"


def _synthesize_fallback_tone(output_path: Path, duration_sec: float = 3.0) -> None:
    """Generate clean silence audio fallback via FFmpeg."""
    ext = output_path.suffix.lower()
    codec = "libmp3lame" if ext == ".mp3" else "aac"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "aevalsrc=0:s=44100",
        "-t", str(duration_sec),
        "-c:a", codec,
        "-b:a", "128k",
        str(output_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)


def synthesize_voiceover(
    text: str,
    voice_id: str = "af_bella",
    output_path: str | Path = "voiceover.wav",
    speed: float = 1.0,
) -> Dict[str, Any]:
    """
    Synthesize original voiceover narration to an audio file (WAV/AAC/MP3) using local Kokoro.
    Runs 100% offline with zero network calls.
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not text.strip():
        _synthesize_fallback_tone(out_path, 1.0)
        return {
            "output_path": str(out_path),
            "voice_id": voice_id,
            "char_count": 0,
            "duration_sec": 1.0,
            "status": "empty_fallback",
        }

    resolved_voice = resolve_voice_id(voice_id)
    lang = "en-gb" if resolved_voice.startswith("b") else "en-us"

    try:
        kokoro = get_kokoro_engine()
        samples, sample_rate = kokoro.create(
            text=text.strip(),
            voice=resolved_voice,
            speed=speed,
            lang=lang,
        )

        duration_sec = len(samples) / float(sample_rate)

        # Write out to temporary wav if target format is compressed, or write directly
        ext = out_path.suffix.lower()
        if ext in [".wav"]:
            sf.write(str(out_path), samples, sample_rate)
        else:
            temp_wav = out_path.with_suffix(".temp.wav")
            sf.write(str(temp_wav), samples, sample_rate)
            codec = "libmp3lame" if ext == ".mp3" else "aac"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(temp_wav),
                "-c:a", codec,
                "-b:a", "192k",
                "-ar", "44100",
                str(out_path),
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            temp_wav.unlink(missing_ok=True)

        logger.info(f"[Kokoro] Synthesized {len(text)} chars with {resolved_voice} ({duration_sec:.2f}s) -> {out_path.name}")
        return {
            "output_path": str(out_path),
            "voice_id": resolved_voice,
            "char_count": len(text),
            "duration_sec": round(duration_sec, 2),
            "sample_rate": sample_rate,
            "status": "success",
        }
    except Exception as e:
        logger.error(f"[Kokoro] Local TTS synthesis failed: {e}")
        words = text.split()
        est_duration = max(2.0, len(words) / 2.5)
        _synthesize_fallback_tone(out_path, est_duration)
        return {
            "output_path": str(out_path),
            "voice_id": resolved_voice,
            "char_count": len(text),
            "duration_sec": round(est_duration, 2),
            "status": "fallback_generated",
            "error": str(e),
        }
