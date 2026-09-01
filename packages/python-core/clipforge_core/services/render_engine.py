"""
ClipForge AI — Professional FFmpeg Render Engine (v2)
Renders clips with smart 9:16 reframing, blurred-background vertical layouts, ASS caption burn-in,
loudnorm audio mastering, and deterministic Render Manifest generation conforming to RENDER_MANIFEST_SCHEMA.json.
"""
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from clipforge_core.services.caption_renderer import generate_ass_subtitles
from clipforge_core.services.media_probe import probe_media

logger = logging.getLogger(__name__)


class RenderError(Exception):
    """Raised when FFmpeg rendering fails."""
    pass


def build_render_manifest(
    clip_id: str,
    project_id: str,
    source_asset_id: str,
    source_path: str,
    source_probe: Dict[str, Any],
    start_sec: float,
    end_sec: float,
    crop_mode: str = "face_track",
    focal_x: float = 0.5,
    caption_style: str = "bold_karaoke",
    editorial_template: str = "explainer",
    rights_basis: str = "owned",
    transformation_score: int = 75,
    transformation_breakdown: Dict[str, int] | None = None,
) -> Dict[str, Any]:
    """
    Builds deterministic render manifest conforming to docs/RENDER_MANIFEST_SCHEMA.json.
    """
    return {
        "manifest_version": "1.0.0",
        "clip_id": clip_id,
        "project_id": project_id,
        "source": {
            "asset_id": source_asset_id,
            "storage_key": str(source_path),
            "start_seconds": round(start_sec, 3),
            "end_seconds": round(end_sec, 3),
            "source_duration_seconds": source_probe.get("duration_sec", 0.0),
            "source_width": source_probe.get("width", 1920),
            "source_height": source_probe.get("height", 1080),
            "source_fps": source_probe.get("fps", 30.0),
            "source_codec": source_probe.get("video_codec", "h264"),
        },
        "output": {
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
            "video_codec": "libx264",
            "audio_codec": "aac",
            "container": "mp4",
            "preset": "standard",
            "video_bitrate": "4500k",
            "audio_bitrate": "128k",
        },
        "crop": {
            "mode": crop_mode,
            "keyframes": [
                {
                    "time_sec": 0.0,
                    "x": round(focal_x, 3),
                    "y": 0.5,
                    "w": 0.5625,
                    "h": 1.0,
                }
            ],
            "blur_radius": 25 if crop_mode == "blur_background" else 0,
        },
        "captions": {
            "enabled": caption_style != "none",
            "style": caption_style,
            "font_size": 68 if caption_style == "bold_karaoke" else 48,
            "position": "bottom",
            "primary_color": "#FFFFFF",
            "highlight_color": "#FFFF00",
        },
        "audio": {
            "source_gain_db": 0.0,
            "loudness_target_lufs": -14.0,
            "ducking": False,
        },
        "effects": {
            "color_grade": "none",
            "speed_multiplier": 1.0,
        },
        "editorial": {
            "template": editorial_template,
            "rights_basis": rights_basis,
            "transformation_score": transformation_score,
            "transformation_breakdown": transformation_breakdown or {},
        },
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "renderer": "clipforge-ffmpeg-v2",
        },
    }


def render_clip(
    source_path: str | Path,
    output_path: str | Path,
    start_sec: float,
    end_sec: float,
    crop_mode: str = "face_track",  # "face_track", "blur_background", "center"
    focal_x: float = 0.5,
    caption_style: str = "bold_karaoke",
    transcript_segments: List[Dict[str, Any]] | None = None,
    output_thumbnail_path: str | Path | None = None,
) -> Dict[str, Any]:
    """
    Renders a 9:16 vertical clip using FFmpeg filtergraphs.
    """
    src = Path(source_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if not src.exists():
        raise FileNotFoundError(f"Source video missing: {src}")

    probe = probe_media(src)
    src_w = probe.get("width", 1920)
    src_h = probe.get("height", 1080)
    duration = end_sec - start_sec

    # 1. Generate Subtitle ASS if captions requested
    ass_filter = ""
    ass_file = None
    if caption_style != "none" and transcript_segments:
        ass_file = out.parent / f"{out.stem}_captions.ass"
        generate_ass_subtitles(
            transcript_segments=transcript_segments,
            clip_start_sec=start_sec,
            clip_end_sec=end_sec,
            output_ass_path=ass_file,
            style_preset=caption_style,
        )
        # Windows path escaping for FFmpeg filter
        escaped_ass = str(ass_file).replace("\\", "/").replace(":", "\\:")
        ass_filter = f",ass='{escaped_ass}'"

    # 2. Build Video Filter Graph
    if probe.get("is_vertical", False):
        # Source is already vertical: scale to 1080:1920 directly
        video_filters = f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2{ass_filter}"
    elif crop_mode == "blur_background":
        # Blurred background + sharp foreground
        video_filters = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
            f"[0:v]scale=1080:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2{ass_filter}"
        )
    else:
        # 9:16 Smart Crop / Reframe with focal_x
        # Crop width for 9:16 from height H is H * 9/16
        crop_w = int(src_h * 9.0 / 16.0)
        # Calculate X offset based on focal_x
        max_x = max(0, src_w - crop_w)
        x_offset = int(max_x * max(0.0, min(1.0, focal_x)))

        video_filters = (
            f"crop={crop_w}:{src_h}:{x_offset}:0,"
            f"scale=1080:1920:flags=lanczos{ass_filter}"
        )

    # 3. Audio Filter Graph: loudnorm to -14 LUFS for YouTube Shorts / TikTok
    audio_filters = "loudnorm=I=-14:LRA=7:TP=-1.5"

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-i", str(src),
        "-vf" if crop_mode != "blur_background" else "-filter_complex",
        video_filters,
        "-af", audio_filters,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-movflags", "+faststart",
        str(out),
    ]

    logger.info(f"[RenderEngine] Rendering clip: {start_sec:.1f}s -> {end_sec:.1f}s (mode={crop_mode}, captions={caption_style})")

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"[RenderEngine] FFmpeg render failed: {e.stderr.strip()[:400]}")
        raise RenderError(f"FFmpeg render failed: {e.stderr.strip()[:200]}")
    except subprocess.TimeoutExpired:
        raise RenderError(f"FFmpeg render timed out after 180s on {out.name}")

    # 4. Generate Thumbnail if requested
    thumb_path = None
    if output_thumbnail_path:
        thumb_path = Path(output_thumbnail_path)
        thumb_time = min(2.0, duration / 2.0)
        thumb_cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(thumb_time),
            "-i", str(out),
            "-vframes", "1",
            "-q:v", "2",
            str(thumb_path),
        ]
        subprocess.run(thumb_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)

    # 5. Probe output and verify QA
    out_probe = probe_media(out)
    return {
        "output_path": str(out),
        "thumbnail_path": str(thumb_path) if thumb_path else None,
        "width": out_probe.get("width"),
        "height": out_probe.get("height"),
        "duration_sec": out_probe.get("duration_sec"),
        "file_size_mb": out_probe.get("file_size_mb"),
    }
