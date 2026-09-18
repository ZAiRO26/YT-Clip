"""
ClipForge AI — Professional FFmpeg Render Engine (v2)
Renders clips with smart 9:16 reframing, blurred-background vertical layouts, ASS caption burn-in,
loudnorm audio mastering, and deterministic Render Manifest generation conforming to RENDER_MANIFEST_SCHEMA.json.
"""
import asyncio
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

from clipforge_core.services.caption_renderer import generate_ass_subtitles
from clipforge_core.services.media_probe import probe_media

logger = logging.getLogger(__name__)


class RenderError(Exception):
    """Raised when FFmpeg rendering fails."""
    pass


def _build_dynamic_crop_expr(
    focal_timeline: List[Dict[str, Any]],
    clip_start_sec: float,
    clip_end_sec: float,
    src_w: int,
    bot_crop_w: int,
    max_keyframes: int = 60,
) -> str:
    """
    Build an FFmpeg crop x-expression for per-frame dynamic speaker tracking.

    Converts focal_timeline entries into a piecewise-linear interpolation
    expression evaluated on every frame using the 't' presentation timestamp.
    Commas in expressions are escaped with \\, for FFmpeg filter syntax compatibility.
    """
    points = []
    for pt in focal_timeline:
        abs_t = pt.get("time_sec", 0.0)
        if clip_start_sec <= abs_t <= clip_end_sec:
            rel_t = round(abs_t - clip_start_sec, 3)
            focal_x = max(0.0, min(1.0, float(pt.get("focal_x", 0.5))))
            face_cx = focal_x * src_w
            x_off = int(max(0, min(src_w - bot_crop_w, face_cx - bot_crop_w / 2.0)))
            points.append((rel_t, x_off))

    if not points:
        return str(int(max(0, (src_w - bot_crop_w) / 2)))

    points.sort(key=lambda p: p[0])

    # Ensure bounds cover [0.0, clip_duration]
    clip_dur = round(clip_end_sec - clip_start_sec, 3)
    if points[0][0] > 0.0:
        points.insert(0, (0.0, points[0][1]))
    if points[-1][0] < clip_dur:
        points.append((clip_dur, points[-1][1]))

    # Downsample if more than max_keyframes
    if len(points) > max_keyframes:
        step = len(points) / float(max_keyframes)
        points = [points[min(len(points) - 1, int(i * step))] for i in range(max_keyframes)]

    if len(points) == 1:
        return str(points[0][1])

    # Build nested if(lt(t\,t1)\,lerp\,else) expression from back to front
    expr = str(points[-1][1])
    for i in range(len(points) - 2, -1, -1):
        t0, x0 = points[i]
        t1, x1 = points[i + 1]
        dt = t1 - t0
        if dt < 0.001:
            continue
        lerp = f"{x0}+({x1}-{x0})*(t-{t0})/{dt:.3f}"
        expr = f"if(lt(t\\,{t1})\\,{lerp}\\,{expr})"

    return expr


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
    focal_timeline: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """
    Builds deterministic render manifest conforming to docs/RENDER_MANIFEST_SCHEMA.json.
    """
    src_w = source_probe.get("width", 1920)
    src_h = source_probe.get("height", 1080)
    crop_w_px = int(src_h * 9 / 16)  # 9:16 crop width from source height
    crop_h_px = src_h
    face_center_x = max(0.0, min(1.0, focal_x)) * src_w
    crop_x_px = int(max(0, min(src_w - crop_w_px, face_center_x - (crop_w_px / 2.0))))
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

    crop_obj: Dict[str, Any] = {
        "mode": crop_mode if crop_mode in ["center", "face_track", "manual", "blur_background", "stacked_speaker"] else "center",
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
    }
    if crop_mode == "stacked_speaker":
        crop_obj["layout_bands"] = {
            "top_height": 710,
            "divider_height": 2,
            "bottom_height": 1210,
            "tracking": "per_frame_dynamic" if (focal_timeline and len(focal_timeline) > 0) else "static_fallback",
        }

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
        "crop": crop_obj,
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
    crop_mode: str = "face_track",  # "face_track", "blur_background", "center", "stacked_speaker"
    focal_x: float = 0.5,
    focal_timeline: List[Dict[str, Any]] | None = None,
    caption_style: str = "bold_karaoke",
    transcript_segments: List[Dict[str, Any]] | None = None,
    output_thumbnail_path: str | Path | None = None,
    progress_callback: Callable[[float], None] | None = None,
) -> Dict[str, Any]:
    """
    Renders a 9:16 vertical clip using FFmpeg filtergraphs.
    Supports smart face crop, background blur, center crop, and stacked context + speaker layouts.
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
    layout_mode = "stacked_speaker" if crop_mode == "stacked_speaker" else "standard"
    if caption_style != "none" and transcript_segments:
        ass_file = out.parent / f"{out.stem}_captions.ass"
        generate_ass_subtitles(
            transcript_segments=transcript_segments,
            clip_start_sec=start_sec,
            clip_end_sec=end_sec,
            output_ass_path=ass_file,
            style_preset=caption_style,
            layout_mode=layout_mode,
        )
        # Windows path escaping for FFmpeg filter
        escaped_ass = ass_file.resolve().as_posix().replace(":", "\\:")
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
    elif crop_mode == "stacked_speaker":
        # Stacked context (37% top = 710px) + active speaker zoom (63% bottom = 1210px)
        TOP_H = 710
        BOT_H = 1210
        DIV_H = 2

        bot_aspect = 1080.0 / float(BOT_H)
        bot_crop_w = int(src_h * bot_aspect // 2 * 2)  # Even width
        bot_crop_h = src_h

        if focal_timeline and len(focal_timeline) > 0:
            crop_x_expr = _build_dynamic_crop_expr(
                focal_timeline, start_sec, end_sec, src_w, bot_crop_w
            )
        else:
            face_center_x = max(0.0, min(1.0, focal_x)) * src_w
            crop_x_expr = str(int(max(0, min(src_w - bot_crop_w, face_center_x - bot_crop_w / 2.0))))

        video_filters = (
            f"[0:v]split=2[top_src][bot_src];"
            f"[top_src]scale=1080:-2,pad=1080:{TOP_H}:(ow-iw)/2:(oh-ih)/2:black[top];"
            f"[bot_src]crop=w={bot_crop_w}:h={bot_crop_h}:x='{crop_x_expr}':y=0,scale=1080:{BOT_H}[bot];"
            f"[top][bot]vstack=inputs=2[stacked];"
            f"[stacked]drawbox=y=709:w=1080:h={DIV_H}:c=white@0.8:t=fill{ass_filter}"
        )
    else:
        # 9:16 Smart Crop / Reframe with focal_x
        # Crop width for 9:16 from height H is H * 9/16
        crop_w = int(src_h * 9.0 / 16.0)
        face_center_x = max(0.0, min(1.0, focal_x)) * src_w
        max_x = max(0, src_w - crop_w)
        x_offset = int(max(0, min(max_x, face_center_x - (crop_w / 2.0))))

        video_filters = (
            f"crop={crop_w}:{src_h}:{x_offset}:0,"
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2{ass_filter}"
        )

    # 3. Audio Filter Graph: loudnorm to -14 LUFS for YouTube Shorts / TikTok
    audio_filters = "loudnorm=I=-14:LRA=7:TP=-1.5"

    filter_script_file = None
    if crop_mode == "stacked_speaker":
        filter_script_file = out.parent / f"{out.stem}_filter_complex.txt"
        filter_script_file.write_text(video_filters, encoding="utf-8")
        filter_args = ["-filter_complex_script", str(filter_script_file)]
    elif crop_mode == "blur_background":
        filter_args = ["-filter_complex", video_filters]
    else:
        filter_args = ["-vf", video_filters]

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-i", str(src),
        *filter_args,
        "-af", audio_filters,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        str(out),
    ]

    logger.info(f"[RenderEngine] Rendering clip: {start_sec:.1f}s -> {end_sec:.1f}s (mode={crop_mode}, captions={caption_style})")

    async def _run_ffmpeg_async():
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stderr_output = []
        
        async def read_stderr():
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                stderr_output.append(line.decode('utf-8'))
                
        async def read_stdout():
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode('utf-8').strip()
                if line_str.startswith("out_time_ms="):
                    try:
                        time_ms = int(line_str.split("=")[1])
                        if duration > 0:
                            percent = min(100.0, (time_ms / 1000000.0) / duration * 100)
                            if progress_callback:
                                progress_callback(percent)
                    except ValueError:
                        pass
                        
        await asyncio.gather(read_stderr(), read_stdout())
        await process.wait()
        
        if process.returncode != 0:
            error_details = "".join(stderr_output[-20:])
            logger.error(f"[RenderEngine] FFmpeg render failed: {error_details[:400]}")
            raise RenderError(f"FFmpeg render failed: {error_details[:200]}")

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(lambda: asyncio.run(_run_ffmpeg_async()))
                future.result()
        else:
            asyncio.run(_run_ffmpeg_async())
    except asyncio.TimeoutError:
        raise RenderError(f"FFmpeg render timed out on {out.name}")
    finally:
        if filter_script_file and filter_script_file.exists():
            try:
                filter_script_file.unlink()
            except Exception:
                pass

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
