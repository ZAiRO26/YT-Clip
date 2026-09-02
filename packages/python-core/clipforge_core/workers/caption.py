"""
ClipForge AI — Caption Worker

Pipeline stage 5: Burn animated captions into cropped clips.

Per TRD section 2 and user requirements:
- Uses captacity for burned-in animated captions
- Caption style configurable per project (per App Flow's New Project screen)
- Styles: bold_karaoke, minimal, subtitle, none

Output: {MEDIA_DIR}/{project_id}/clips/{clip_index}_final.mp4

Celery queue: caption (concurrency=2 in production, CPU-bound)
"""

import logging
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from clipforge_core.celery_app import celery_app
from clipforge_core.config import settings
from clipforge_core.database import get_sync_session
from clipforge_core.models import Job, Project

logger = logging.getLogger(__name__)

# Caption style presets
CAPTION_STYLES = {
    "bold_karaoke": {
        "font_size": 30,  # Was 60
        "font_color": "white",
        "stroke_color": "black",
        "stroke_width": 3,
        "highlight_current_word": True,
        "highlight_color": "#F97316",  # ClipForge accent orange
        "position": "bottom",
        "animation": "pop",
    },
    "minimal": {
        "font_size": 22,  # Was 42
        "font_color": "white",
        "stroke_color": "black",
        "stroke_width": 1,
        "highlight_current_word": False,
        "highlight_color": None,
        "position": "bottom",
        "animation": "fade",
    },
    "subtitle": {
        "font_size": 18,  # Was 36
        "font_color": "white",
        "stroke_color": "black",
        "stroke_width": 2,
        "highlight_current_word": False,
        "highlight_color": None,
        "position": "bottom",
        "animation": "none",
    },
    "none": None,  # Skip captioning entirely
}


def _update_job_status(
    project_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update the caption job status in the database."""
    session = get_sync_session()
    try:
        job = (
            session.query(Job)
            .filter(
                Job.project_id == uuid.UUID(project_id),
                Job.stage == "caption",
            )
            .first()
        )
        if job:
            job.status = status
            job.error_message = error_message
            if status == "running":
                job.started_at = datetime.now(timezone.utc)
            if status in ("success", "failed"):
                job.completed_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as e:
        logger.error(f"Failed to update job status: {e}")
        session.rollback()
    finally:
        session.close()


def _update_project_status(project_id: str, status: str) -> None:
    """Update the project-level status."""
    session = get_sync_session()
    try:
        project = (
            session.query(Project)
            .filter(
                Project.id == uuid.UUID(project_id),
            )
            .first()
        )
        if project:
            project.status = status
            session.commit()
    except Exception as e:
        logger.error(f"Failed to update project status: {e}")
        session.rollback()
    finally:
        session.close()


def _caption_with_captacity(
    input_path: str,
    output_path: str,
    style_config: dict,
) -> bool:
    """
    Add captions using captacity.

    captacity handles:
    - Transcribing the clip audio (word-level timestamps)
    - Rendering animated text overlays
    - Burning them into the video
    """
    try:
        import captacity

        logger.info(f"Adding captions with captacity: {Path(input_path).name}")

        captacity.add_captions(
            video_file=input_path,
            output_file=output_path,
            font_size=style_config.get("font_size", 60),
            font_color=style_config.get("font_color", "white"),
            stroke_color=style_config.get("stroke_color", "black"),
            stroke_width=style_config.get("stroke_width", 3),
            highlight_current_word=style_config.get("highlight_current_word", True),
            word_highlight_color=style_config.get("highlight_color"),
            position=style_config.get("position", ("center", "bottom")),
        )

        return Path(output_path).exists()

    except ImportError:
        logger.warning("captacity not available")
        return False
    except Exception as e:
        logger.warning(f"captacity failed: {e}")
        return False


def _caption_with_ffmpeg_srt(
    input_path: str,
    output_path: str,
    style_config: dict,
) -> bool:
    """
    Fallback: Generate SRT from the clip's audio and burn with ffmpeg.

    Uses faster-whisper to transcribe the clip, generates SRT with
    full sentence segments (not word-by-word), then burns with ffmpeg.
    """
    try:
        from faster_whisper import WhisperModel

        # Transcribe the clip
        model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )

        segments_iter, info = model.transcribe(
            input_path,
            beam_size=3,
            word_timestamps=False,
            vad_filter=True,
        )

        # Build SRT content with full segments (not word-by-word)
        srt_lines = []
        subtitle_index = 1

        for segment in segments_iter:
            text = segment.text.strip()
            if not text:
                continue

            start_h = int(segment.start // 3600)
            start_m = int((segment.start % 3600) // 60)
            start_s = int(segment.start % 60)
            start_ms = int((segment.start % 1) * 1000)

            end_h = int(segment.end // 3600)
            end_m = int((segment.end % 3600) // 60)
            end_s = int(segment.end % 60)
            end_ms = int((segment.end % 1) * 1000)

            srt_lines.append(str(subtitle_index))
            srt_lines.append(
                f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> "
                f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
            )
            srt_lines.append(text)
            srt_lines.append("")
            subtitle_index += 1

        if not srt_lines:
            logger.warning("No speech detected in clip")
            return False

        # Write SRT file
        srt_path = str(Path(input_path).with_suffix(".srt"))
        Path(srt_path).write_text("\n".join(srt_lines), encoding="utf-8")

        # Burn subtitles with ffmpeg
        font_size = style_config.get("font_size", 24)

        # Use ffmpeg subtitles filter - need to escape path for Windows
        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")

        # Use Fontstyle that supports Devanagari/Hindi and other non-Latin scripts
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-vf",
            f"subtitles='{srt_escaped}':force_style='FontName=Noto Sans,FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Alignment=2,MarginV=40'",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "copy",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        # Clean up SRT
        Path(srt_path).unlink(missing_ok=True)

        if result.returncode != 0:
            logger.warning(f"ffmpeg subtitle burn failed: {result.stderr[-300:]}")
            return False

        return Path(output_path).exists()

    except Exception as e:
        logger.warning(f"SRT fallback failed: {e}")
        return False


def caption_clip(
    input_path: str,
    output_path: str,
    caption_style: str,
) -> dict:
    """
    Add captions to a single clip.

    Args:
        input_path: Path to cropped clip
        output_path: Path for final captioned clip
        caption_style: Style preset name from CAPTION_STYLES

    Returns:
        dict with caption info
    """
    style_config = CAPTION_STYLES.get(caption_style)

    # Handle "none" style — just copy the file
    if style_config is None:
        shutil.copy2(input_path, output_path)
        return {
            "output_path": output_path,
            "method": "none",
            "caption_style": caption_style,
        }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Try captacity first
    success = _caption_with_captacity(input_path, output_path, style_config)

    if success:
        method = "captacity"
    else:
        # Fallback to ffmpeg + SRT
        logger.info("Falling back to ffmpeg SRT captions")
        success = _caption_with_ffmpeg_srt(input_path, output_path, style_config)
        method = "ffmpeg_srt" if success else "none"

    if not success:
        # Ultimate fallback — just copy without captions
        logger.warning(f"All caption methods failed for {input_path}. Copying without captions.")
        shutil.copy2(input_path, output_path)
        method = "none_fallback"

    file_size = Path(output_path).stat().st_size

    return {
        "output_path": output_path,
        "method": method,
        "caption_style": caption_style,
        "file_size_mb": round(file_size / (1024 * 1024), 2),
    }


@celery_app.task(
    name="app.workers.caption.caption_clips",
    queue="editorial",
    bind=True,
    max_retries=1,
    default_retry_delay=15,
)
def caption_clips(
    self,
    project_id: str,
    cropped_clips: list[dict],
    caption_style: str,
) -> dict:
    """
    Add captions to all cropped clips for a project.

    Args:
        project_id: UUID of the project
        cropped_clips: List of clip dicts from crop worker (with output_path, score, etc.)
        caption_style: Style preset name

    Returns:
        dict with list of final clip paths

    Does NOT fail the whole job if captioning fails on one clip.
    """
    logger.info(f"[Caption] Starting for project {project_id}: {len(cropped_clips)} clips, style={caption_style}")

    _update_job_status(project_id, "running")
    _update_project_status(project_id, "captioning")

    final_clips = []
    failed_clips = []

    try:
        for clip in cropped_clips:
            cropped_path = clip["output_path"]
            index = clip.get("index", 0)

            # Final output path
            final_filename = f"clip_{index:03d}_final.mp4"
            final_path = str(Path(cropped_path).parent / final_filename)

            try:
                caption_result = caption_clip(
                    input_path=cropped_path,
                    output_path=final_path,
                    caption_style=caption_style,
                )

                # Generate thumbnail
                thumbnail_filename = f"clip_{index:03d}_thumb.jpg"
                thumbnail_path = str(Path(cropped_path).parent / thumbnail_filename)

                try:
                    import subprocess

                    subprocess.run(
                        ["ffmpeg", "-y", "-i", final_path, "-vframes", "1", "-q:v", "2", thumbnail_path],
                        check=True,
                        capture_output=True,
                    )
                    # Create relative path for frontend like we do for clips
                    # final_path looks like D:\...\backend\media\project_id\clips\clip_000_final.mp4
                    # We need to save the relative path: media/project_id/clips/clip_000_thumb.jpg
                    rel_thumb_path = Path(thumbnail_path).relative_to(settings.MEDIA_DIR.parent).as_posix()
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail for clip {index}: {e}")
                    rel_thumb_path = None

                final_clip = {
                    **clip,
                    "final_path": caption_result["output_path"],
                    "thumbnail_url": rel_thumb_path,
                    "caption_method": caption_result["method"],
                    "caption_style": caption_result["caption_style"],
                    "final_size_mb": caption_result["file_size_mb"],
                }
                final_clips.append(final_clip)

                logger.info(f"[Caption] Clip {index}: {caption_result['method']} ({caption_result['file_size_mb']} MB)")

            except Exception as e:
                logger.error(f"[Caption] Failed on clip {index}: {e}")
                failed_clips.append(
                    {
                        "index": index,
                        "error": str(e),
                    }
                )

        if not final_clips:
            error_msg = f"All {len(cropped_clips)} clips failed captioning"
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise RuntimeError(error_msg)

        result = {
            "project_id": project_id,
            "clips": final_clips,
            "failed": failed_clips,
            "total_captioned": len(final_clips),
            "total_failed": len(failed_clips),
            "caption_style": caption_style,
        }

        # Mark job and project as done
        _update_job_status(project_id, "success")
        _update_project_status(project_id, "done")

        logger.info(
            f"[Caption] Complete for project {project_id}: {len(final_clips)} captioned, {len(failed_clips)} failed"
        )

        return result

    except RuntimeError:
        raise
    except Exception as e:
        error_msg = f"Caption error: {e}"
        logger.error(f"[Caption] Error for project {project_id}: {error_msg}")

        if self.request.retries < self.max_retries:
            _update_job_status(project_id, "retrying", error_message=error_msg)
            raise self.retry(exc=e)
        else:
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise
