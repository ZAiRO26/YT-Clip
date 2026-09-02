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
    source_risk_label: str = "lower_workflow_risk",
    transformation_score: int = 75,
    transformation_breakdown: Dict[str, int] | None = None,
    effect_layers: List[Dict[str, Any]] | None = None,
    render_duration_sec: float | None = None,
    audio_mode: str = "original_only",
    voiceover_asset_id: str | None = None,
) -> Dict[str, Any]:
    """
    Builds deterministic render manifest conforming to docs/RENDER_MANIFEST_SCHEMA.json.
    """
    src_w = source_probe.get("width", 1920)
    src_h = source_probe.get("height", 1080)
    crop_w_px = int(src_h * 9 / 16)  # 9:16 crop width from source height
    crop_h_px = src_h
    crop_x_px = int(max(0, src_w - crop_w_px) * max(0.0, min(1.0, focal_x)))
    crop_y_px = 0

    # Map editorial template if needed
    ed_template = editorial_template
    if ed_template == "campaign_promo":
        ed_template = "campaign_promotion"
    if ed_template not in ["explainer", "commentary", "news_context", "reaction_pip", "quote_breakdown", "campaign_promotion"]:
        ed_template = "explainer"

    # Map transformation breakdown to canonical schema keys with strict range bounds
    tb = transformation_breakdown or {}
    canon_tb = {
        "rights_completeness": min(25, max(0, int(tb.get("rights_completeness", tb.get("narrative_structure", 20))))),
        "editorial_contribution": min(30, max(0, int(tb.get("editorial_contribution", tb.get("commentary_depth", 22))))),
        "visual_transformation": min(20, max(0, int(tb.get("visual_transformation", tb.get("visual_alteration", 20))))),
        "clip_uniqueness": min(15, max(0, int(tb.get("clip_uniqueness", tb.get("source_exclusivity", 14))))),
        "human_review": min(10, max(0, int(tb.get("human_review", tb.get("editorial_callouts", 10))))),
    }

    # Format schema-compliant effect layers
    formatted_layers = []
    if effect_layers:
        for eff in effect_layers:
            eff_type = eff.get("type") or eff.get("id") or eff.get("effect_id", "")
            if eff_type == "zoom":
                eff_type = "punch_in_zoom"
            if eff_type in [
                "punch_in_zoom", "camera_shake", "film_grain", "vignette",
                "speed_ramp", "rgb_split", "vhs_noise", "background_blur",
                "pixelate", "overlay_asset", "floating_cta", "dvd_bounce", "cta_lower_third"
            ]:
                formatted_layers.append({
                    "type": eff_type,
                    "enabled": eff.get("enabled", True),
                    "intensity": min(1.0, max(0.0, float(eff.get("intensity", 0.5)))),
                })

    has_vo = (voiceover_asset_id is not None and str(voiceover_asset_id).strip() != "") or audio_mode in ["mix", "voiceover_only"]
    manifest_audio_mode = audio_mode if audio_mode in ["original_only", "voiceover_only", "mix", "mute_original_keep_ambient"] else ("mix" if has_vo else "original_only")

    metadata_obj = {
        "renderer_version": "0.2.0",
        "rendered_at": datetime.now(timezone.utc).isoformat(),
        "transformation_score": transformation_score,
        "transformation_breakdown": canon_tb,
        "rights_basis": rights_basis,
        "source_risk_label": source_risk_label if source_risk_label in ["lower_workflow_risk", "needs_review", "high_claim_risk", "unknown"] else "lower_workflow_risk",
    }
    if render_duration_sec is not None:
        metadata_obj["render_duration_seconds"] = float(render_duration_sec)

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
            "source_width": src_w,
            "source_height": src_h,
            "source_fps": source_probe.get("fps", 30.0),
            "source_codec": source_probe.get("video_codec", "h264"),
        },
        "output": {
            "aspect_ratio": "9:16",
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
            "mode": crop_mode if crop_mode in ["center", "face_track", "manual", "blur_background"] else "center",
            "keyframes": [
                {
                    "time_sec": 0.0,
                    "x": crop_x_px,
                    "y": crop_y_px,
                    "w": crop_w_px,
                    "h": crop_h_px,
                }
            ],
            "safe_text_zone": True,
        },
        "captions": {
            "enabled": caption_style != "none",
            "preset": caption_style if caption_style in ["bold_karaoke", "minimal", "clean_subtitle", "none"] else "bold_karaoke",
            "font_size": 68 if caption_style == "bold_karaoke" else 48,
            "position": "lower_safe_zone",
            "font_color": "#FFFFFF",
        },
        "audio": {
            "mode": manifest_audio_mode,
            "original_volume": 100,
            "voiceover_volume": 100 if has_vo else 0,
            "background_music_volume": 0,
            "voiceover_asset_id": str(voiceover_asset_id) if (has_vo and voiceover_asset_id) else None,
            "duck_original_under_voiceover": has_vo,
            "normalize_loudness": True,
            "target_lufs": -14.0,
        },
        "effects": {
            "safe_zones": True,
            "layers": formatted_layers,
        },
        "editorial": {
            "template": ed_template,
            "hook_text": None,
            "narration_script": None,
            "narration_status": "none",
            "requires_human_fact_check": False,
            "callout_labels": [],
            "source_attribution": None,
            "cta_text": None,
        },
        "metadata": metadata_obj,
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
