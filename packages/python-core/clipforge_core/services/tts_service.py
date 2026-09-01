"""
ClipForge AI — Voiceover TTS Synthesis Engine (v2)
Zero-cost inference local/edge TTS adapter supporting multiple studio voice personas.

Voice Personas:
- en-US-JennyNeural (Bella — Warm Explainer, US Female)
- en-US-GuyNeural (Adam — Dynamic Host, US Male)
- en-GB-SoniaNeural (Emma — British Commentary, UK Female)
- en-GB-RyanNeural (George — British Documentary, UK Male)
- en-US-AriaNeural (Sarah — Authoritative News, US Female)
"""
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

VOICE_PERSONAS: List[Dict[str, str]] = [
    {
        "id": "en-US-JennyNeural",
        "name": "Bella",
        "description": "Warm & Engaging Explainer",
        "accent": "American",
        "gender": "Female",
    },
    {
        "id": "en-US-GuyNeural",
        "name": "Adam",
        "description": "Dynamic & Authoritative Host",
        "accent": "American",
        "gender": "Male",
    },
    {
        "id": "en-GB-SoniaNeural",
        "name": "Emma",
        "description": "Thoughtful News & Commentary",
        "accent": "British",
        "gender": "Female",
    },
    {
        "id": "en-GB-RyanNeural",
        "name": "George",
        "description": "Documentary & Storyteller",
        "accent": "British",
        "gender": "Male",
    },
    {
        "id": "en-US-AriaNeural",
        "name": "Sarah",
        "description": "Clear & Polished Narrator",
        "accent": "American",
        "gender": "Female",
    },
]


async def _synthesize_edge_tts(text: str, voice: str, output_path: Path) -> None:
    """Synthesize using edge-tts async API."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def _synthesize_fallback_tone(output_path: Path, duration_sec: float = 3.0) -> None:
    """Generate clean silence/tone audio fallback via FFmpeg."""
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
    voice_id: str = "en-US-JennyNeural",
    output_path: str | Path = "voiceover.mp3",
) -> Dict[str, Any]:
    """
    Synthesize original voiceover narration to MP3/AAC audio file.
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not text.strip():
        _synthesize_fallback_tone(out_path, 1.0)
        return {
            "output_path": str(out_path),
            "voice_id": voice_id,
            "char_count": 0,
            "status": "empty_fallback",
        }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_synthesize_edge_tts(text, voice_id, out_path))
        finally:
            loop.close()

        logger.info(f"[TTS] Synthesized {len(text)} chars with {voice_id} -> {out_path.name}")
        return {
            "output_path": str(out_path),
            "voice_id": voice_id,
            "char_count": len(text),
            "status": "success",
        }
    except Exception as e:
        logger.warning(f"[TTS] Edge-TTS synthesis failed ({e}), using audio fallback")
        # Estimate duration based on reading speed (~150 words per minute = 2.5 words/sec)
        words = text.split()
        est_duration = max(2.0, len(words) / 2.5)
        _synthesize_fallback_tone(out_path, est_duration)
        return {
            "output_path": str(out_path),
            "voice_id": voice_id,
            "char_count": len(text),
            "status": "fallback_generated",
            "error": str(e),
        }
