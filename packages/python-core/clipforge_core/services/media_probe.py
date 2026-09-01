"""
ClipForge AI — Media Metadata Extractor (ffprobe)
Extracts deterministic video/audio properties and validates input streams.
"""
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ProbeError(Exception):
    """Raised when ffprobe execution fails or output is unreadable."""
    pass


def parse_fps(r_frame_rate: str) -> float:
    """Parse fractional frame rate string (e.g., '30000/1001' or '30/1') to float."""
    try:
        if "/" in r_frame_rate:
            num, den = r_frame_rate.split("/")
            return round(float(num) / float(den), 2)
        return round(float(r_frame_rate), 2)
    except Exception:
        return 30.0


def probe_media(file_path: str | Path) -> Dict[str, Any]:
    """
    Run ffprobe against a local media file and return structured technical metadata.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Media file does not exist: {path}")

    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
            check=True,
        )
        data = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        raise ProbeError(f"ffprobe timed out on {path}")
    except subprocess.CalledProcessError as e:
        raise ProbeError(f"ffprobe failed ({e.returncode}): {e.stderr.strip()}")
    except json.JSONDecodeError as e:
        raise ProbeError(f"ffprobe JSON decode error: {e}")
    except FileNotFoundError:
        raise ProbeError("ffprobe binary not found in system PATH. Ensure FFmpeg is installed.")

    streams = data.get("streams", [])
    format_info = data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video_stream:
        raise ProbeError(f"No video stream found in media file: {path}")

    # Duration from format or streams
    duration = 0.0
    if "duration" in format_info:
        try:
            duration = float(format_info["duration"])
        except ValueError:
            pass
    if duration == 0.0 and video_stream and "duration" in video_stream:
        try:
            duration = float(video_stream["duration"])
        except ValueError:
            pass

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    fps = parse_fps(video_stream.get("r_frame_rate", "30/1"))
    video_codec = video_stream.get("codec_name", "unknown")

    audio_codec = audio_stream.get("codec_name") if audio_stream else None
    has_audio = audio_stream is not None
    audio_channels = int(audio_stream.get("channels", 0)) if audio_stream else 0
    audio_sample_rate = int(audio_stream.get("sample_rate", 0)) if audio_stream else 0

    file_size = int(format_info.get("size", path.stat().st_size if path.exists() else 0))
    bitrate = int(format_info.get("bit_rate", 0))

    return {
        "file_path": str(path),
        "duration_sec": round(duration, 3),
        "width": width,
        "height": height,
        "aspect_ratio": f"{width}:{height}" if width and height else "unknown",
        "is_vertical": height > width,
        "fps": fps,
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "has_audio": has_audio,
        "audio_channels": audio_channels,
        "audio_sample_rate": audio_sample_rate,
        "file_size_bytes": file_size,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "bitrate_kbps": round(bitrate / 1000) if bitrate else 0,
        "raw_format": format_info,
    }
