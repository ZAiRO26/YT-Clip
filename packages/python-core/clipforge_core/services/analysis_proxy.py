"""
ClipForge AI — Analysis Proxy

Scene detection and face tracking only produce timestamps and normalized face
positions, and the face tracker already shrinks every frame to 480x270. Decoding
the full-resolution source for them (twice) is the slowest part of the pipeline,
so they read a small 540p H.264 copy instead. The copy keeps every frame and the
exact frame rate so all timestamps line up with the source. Rendering never uses it.
"""
import logging
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from clipforge_core.services.media_probe import probe_media

logger = logging.getLogger(__name__)

PROXY_HEIGHT = 540  # exact 2x of the face tracker's 270p working size


def create_analysis_proxy(
    source_path: str | Path,
    output_path: str | Path,
    progress_callback: Optional[Callable[[float, str], Any]] = None,
) -> Optional[Path]:
    """
    Build the analysis copy. Returns its path, or None when the source is already
    small or anything goes wrong — callers then analyse the source directly.
    """
    src, out = Path(source_path), Path(output_path)
    try:
        probe = probe_media(src)
        if int(probe.get("height", 0)) <= PROXY_HEIGHT:
            return None
        duration = float(probe.get("duration_sec", 0.0)) or 1.0

        cmd = [
            "ffmpeg", "-y", "-v", "error", "-progress", "pipe:1", "-nostats",
            "-i", str(src),
            "-an",
            "-vf", f"scale=-2:{PROXY_HEIGHT}",
            "-fps_mode", "passthrough",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            str(out),
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        last_reported = -5.0
        for line in proc.stdout:  # type: ignore[union-attr]
            if progress_callback and line.startswith("out_time_ms="):
                value = line.split("=", 1)[1].strip()
                if value.isdigit():
                    pct = min(100.0, int(value) / 1_000_000 / duration * 100.0)
                    if pct - last_reported >= 5.0:
                        last_reported = pct
                        progress_callback(pct, f"Preparing fast analysis copy ({int(pct)}%)")
        stderr = proc.stderr.read() if proc.stderr else ""
        if proc.wait() != 0 or not out.exists() or out.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg failed: {stderr[-300:]}")

        # Timestamps are only trustworthy if the copy spans the same timeline as the source.
        # (Container frame counts are not compared: files with edit lists report extra frames.)
        proxy_duration = float(probe_media(out).get("duration_sec", 0.0))
        if abs(proxy_duration - duration) > 0.5:
            raise RuntimeError(f"duration mismatch (source {duration:.2f}s, proxy {proxy_duration:.2f}s)")

        logger.info(f"[AnalysisProxy] Built {out.name} ({out.stat().st_size / 1_048_576:.0f} MB) for {src.name}")
        return out
    except Exception as e:
        logger.warning(f"[AnalysisProxy] Falling back to full-resolution analysis: {e}")
        out.unlink(missing_ok=True)
        return None
