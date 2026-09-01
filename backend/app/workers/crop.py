"""
ClipForge AI — Crop/Encode Worker

Pipeline stage 4: Crop source video segments to vertical format.

Per TRD section 2 and user requirements:
- Uses ClipsAI for face/speaker-tracked vertical reframing
- Falls back to center-crop if ClipsAI fails on a given source video
- Does NOT fail the whole job if ClipsAI errors on one clip
- Supports 9:16, 1:1, and 16:9 aspect ratios

Output: {MEDIA_DIR}/{project_id}/clips/{clip_index}_cropped.mp4

Celery queue: crop (concurrency=2 in production, CPU-bound)
"""
import json
import logging
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.celery_app import celery_app
from app.config import settings
from app.database import get_sync_session
from app.models import Job, Project

logger = logging.getLogger(__name__)

# Aspect ratio to width:height mappings (for 1080p base)
ASPECT_RATIOS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}


def _update_job_status(
    project_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update the crop job status in the database."""
    session = get_sync_session()
    try:
        job = session.query(Job).filter(
            Job.project_id == uuid.UUID(project_id),
            Job.stage == "crop",
        ).first()
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
        project = session.query(Project).filter(
            Project.id == uuid.UUID(project_id),
        ).first()
        if project:
            project.status = status
            session.commit()
    except Exception as e:
        logger.error(f"Failed to update project status: {e}")
        session.rollback()
    finally:
        session.close()


def _center_crop_ffmpeg(
    source_path: str,
    output_path: str,
    start_sec: float,
    end_sec: float,
    target_width: int,
    target_height: int,
) -> bool:
    """
    Fallback: center-crop using ffmpeg directly.

    Extracts the segment, scales to fit, and center-crops to target dimensions.
    """
    duration = end_sec - start_sec

    # Build the filter: scale to fit height, then center-crop to exact dimensions
    if target_width < target_height:
        # Portrait (9:16) — scale to match height, crop width
        vf = (
            f"scale=-1:{target_height},"
            f"crop={target_width}:{target_height},"
            f"setsar=1"
        )
    elif target_width == target_height:
        # Square (1:1) — scale to fit the smaller dimension, then crop
        vf = (
            f"scale={target_width}:{target_width}:force_original_aspect_ratio=increase,"
            f"crop={target_width}:{target_height},"
            f"setsar=1"
        )
    else:
        # Landscape (16:9) — just scale
        vf = (
            f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2,"
            f"setsar=1"
        )

    cmd = [
        "ffmpeg",
        "-y",                           # Overwrite output
        "-ss", str(start_sec),          # Seek to start (before input for speed)
        "-i", source_path,
        "-t", str(duration),            # Duration
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per clip
        )

        if result.returncode != 0:
            logger.error(f"ffmpeg failed: {result.stderr[-500:]}")
            return False

        return Path(output_path).exists()

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg timed out after 5 minutes")
        return False
    except FileNotFoundError:
        logger.error("ffmpeg not found. Ensure ffmpeg is installed and in PATH.")
        return False


def _clipsai_crop(
    source_path: str,
    output_path: str,
    start_sec: float,
    end_sec: float,
    aspect_ratio: str,
) -> bool:
    """
    Crop using ClipsAI for face/speaker-tracked vertical reframing.

    Falls back to center-crop on any error.
    """
    try:
        from clipsai import resize

        # ClipsAI resize expects the aspect ratio as a tuple
        ar_map = {
            "9:16": (9, 16),
            "1:1": (1, 1),
            "16:9": (16, 9),
        }
        ar_tuple = ar_map.get(aspect_ratio, (9, 16))

        # First extract the clip segment using ffmpeg
        temp_segment = str(Path(output_path).parent / f"_temp_segment_{Path(output_path).stem}.mp4")
        duration = end_sec - start_sec

        extract_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-i", source_path,
            "-t", str(duration),
            "-c", "copy",
            temp_segment,
        ]

        result = subprocess.run(extract_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning(f"Failed to extract segment for ClipsAI: {result.stderr[-200:]}")
            return False

        # Use ClipsAI to resize with face tracking
        resized = resize.resize_video(
            original_video_path=temp_segment,
            resized_video_path=output_path,
            aspect_ratio=ar_tuple,
        )

        # Clean up temp file
        Path(temp_segment).unlink(missing_ok=True)

        return Path(output_path).exists()

    except ImportError:
        logger.warning("ClipsAI not available, falling back to center-crop")
        return False
    except Exception as e:
        logger.warning(f"ClipsAI failed: {e}. Falling back to center-crop.")
        # Clean up temp file if it exists
        temp_segment_path = Path(output_path).parent / f"_temp_segment_{Path(output_path).stem}.mp4"
        temp_segment_path.unlink(missing_ok=True)
        return False


def crop_clip(
    source_path: str,
    output_path: str,
    start_sec: float,
    end_sec: float,
    aspect_ratio: str,
    use_clipsai: bool = True,
) -> dict:
    """
    Crop a single clip from the source video.

    Tries ClipsAI first for face-tracked cropping, falls back to center-crop.

    Args:
        source_path: Path to source video
        output_path: Path for output clip
        start_sec: Start time in seconds
        end_sec: End time in seconds
        aspect_ratio: Target aspect ratio ('9:16', '1:1', '16:9')
        use_clipsai: Whether to attempt ClipsAI first

    Returns:
        dict with crop info and method used
    """
    target_w, target_h = ASPECT_RATIOS.get(aspect_ratio, (1080, 1920))
    method = "unknown"
    success = False

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Try ClipsAI first
    if use_clipsai:
        logger.info(f"Attempting ClipsAI crop: {start_sec:.1f}s - {end_sec:.1f}s ({aspect_ratio})")
        success = _clipsai_crop(source_path, output_path, start_sec, end_sec, aspect_ratio)
        if success:
            method = "clipsai"

    # Fallback to center-crop
    if not success:
        logger.info(f"Using center-crop fallback: {start_sec:.1f}s - {end_sec:.1f}s ({aspect_ratio})")
        success = _center_crop_ffmpeg(
            source_path, output_path,
            start_sec, end_sec,
            target_w, target_h,
        )
        if success:
            method = "center_crop"

    if not success:
        raise RuntimeError(
            f"Failed to crop clip {start_sec:.1f}s-{end_sec:.1f}s "
            f"using both ClipsAI and center-crop fallback"
        )

    file_size = Path(output_path).stat().st_size

    return {
        "output_path": output_path,
        "method": method,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "duration_sec": round(end_sec - start_sec, 3),
        "aspect_ratio": aspect_ratio,
        "resolution": f"{target_w}x{target_h}",
        "file_size_mb": round(file_size / (1024 * 1024), 2),
    }


@celery_app.task(
    name="app.workers.crop.crop_clips",
    queue="crop",
    bind=True,
    max_retries=1,
    default_retry_delay=15,
)
def crop_clips(
    self,
    project_id: str,
    source_path: str,
    selections: list[dict],
    aspect_ratio: str,
) -> dict:
    """
    Crop all selected segments from the source video.

    Args:
        project_id: UUID of the project
        source_path: Path to the source video
        selections: List of {start_sec, end_sec, score, reasoning}
        aspect_ratio: Target aspect ratio

    Returns:
        dict with list of cropped clip paths and metadata

    Does NOT fail the whole job if one clip fails — skips it and continues.
    """
    logger.info(f"[Crop] Starting for project {project_id}: {len(selections)} clips")

    _update_job_status(project_id, "running")
    _update_project_status(project_id, "encoding")

    clips_dir = Path(source_path).parent / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    cropped_clips = []
    failed_clips = []

    try:
        for i, selection in enumerate(selections):
            clip_filename = f"clip_{i:03d}_cropped.mp4"
            output_path = str(clips_dir / clip_filename)

            try:
                clip_result = crop_clip(
                    source_path=source_path,
                    output_path=output_path,
                    start_sec=selection["start_sec"],
                    end_sec=selection["end_sec"],
                    aspect_ratio=aspect_ratio,
                )
                clip_result["index"] = i
                clip_result["score"] = selection.get("score", 0)
                clip_result["reasoning"] = selection.get("reasoning", "")
                cropped_clips.append(clip_result)

                logger.info(
                    f"[Crop] Clip {i+1}/{len(selections)}: "
                    f"{clip_result['duration_sec']:.1f}s via {clip_result['method']}"
                )

            except Exception as e:
                logger.error(f"[Crop] Failed on clip {i}: {e}")
                failed_clips.append({
                    "index": i,
                    "start_sec": selection["start_sec"],
                    "end_sec": selection["end_sec"],
                    "error": str(e),
                })

        if not cropped_clips:
            error_msg = f"All {len(selections)} clips failed to crop"
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise RuntimeError(error_msg)

        result = {
            "project_id": project_id,
            "clips": cropped_clips,
            "failed": failed_clips,
            "total_cropped": len(cropped_clips),
            "total_failed": len(failed_clips),
        }

        _update_job_status(project_id, "success")
        logger.info(
            f"[Crop] Complete for project {project_id}: "
            f"{len(cropped_clips)} cropped, {len(failed_clips)} failed"
        )

        return result

    except RuntimeError:
        raise
    except Exception as e:
        error_msg = f"Crop error: {e}"
        logger.error(f"[Crop] Error for project {project_id}: {error_msg}")

        if self.request.retries < self.max_retries:
            _update_job_status(project_id, "retrying", error_message=error_msg)
            raise self.retry(exc=e)
        else:
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise
