"""
ClipForge AI — Transcribe Worker

Pipeline stage 2: Transcribe source video using faster-whisper.

Per TRD section 2 and user requirements:
- Uses faster-whisper, CPU-mode by default
- Config flag to switch to GPU later (WHISPER_DEVICE env var)
- Outputs timestamped transcript as JSON (word-level + segment-level)
- Writes granular status to jobs table (transcribe stage)

Output: {MEDIA_DIR}/{project_id}/transcript.json

Celery queue: transcribe (concurrency=2 in production, CPU-bound)
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from faster_whisper import WhisperModel

from clipforge_core.celery_app import celery_app
from clipforge_core.config import settings
from clipforge_core.database import get_sync_session
from clipforge_core.models import Job, Project

logger = logging.getLogger(__name__)

# Module-level model cache — loaded once per worker process
_whisper_model: WhisperModel | None = None


def _get_whisper_model() -> WhisperModel:
    """
    Get or initialize the Whisper model.

    Cached at module level so it's loaded once per Celery worker process,
    not once per task. Model loading is the most expensive part (~5-15s).

    Config from settings:
        WHISPER_MODEL_SIZE: 'tiny', 'base', 'small', 'medium', 'large-v3'
        WHISPER_DEVICE: 'cpu' or 'cuda'
        WHISPER_COMPUTE_TYPE: 'int8', 'float16', 'float32'
    """
    global _whisper_model
    if _whisper_model is None:
        logger.info(
            f"Loading Whisper model: {settings.WHISPER_MODEL_SIZE} "
            f"(device={settings.WHISPER_DEVICE}, compute={settings.WHISPER_COMPUTE_TYPE})"
        )
        _whisper_model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
        logger.info("Whisper model loaded successfully")
    return _whisper_model


def _update_job_status(
    project_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update the transcribe job status in the database."""
    session = get_sync_session()
    try:
        job = (
            session.query(Job)
            .filter(
                Job.project_id == uuid.UUID(project_id),
                Job.stage == "transcribe",
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
        else:
            logger.warning(f"No transcribe job found for project {project_id}")
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


def transcribe_audio(source_path: str, output_dir: str) -> dict:
    """
    Transcribe a video/audio file using faster-whisper.

    Args:
        source_path: Path to the source video file
        output_dir: Directory to write transcript.json

    Returns:
        dict with:
            - segments: list of {start, end, text, words}
            - full_text: concatenated transcript
            - language: detected language
            - duration_sec: total audio duration
    """
    model = _get_whisper_model()
    source = Path(source_path)

    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    logger.info(f"Transcribing: {source.name}")

    # Run transcription
    segments_iter, info = model.transcribe(
        str(source),
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,  # Voice Activity Detection — skip silence
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )

    logger.info(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")

    # Process segments into structured format
    segments = []
    full_text_parts = []

    for segment in segments_iter:
        words = []
        if segment.words:
            for word in segment.words:
                words.append(
                    {
                        "start": round(word.start, 3),
                        "end": round(word.end, 3),
                        "word": word.word.strip(),
                        "probability": round(word.probability, 3),
                    }
                )

        seg_data = {
            "id": len(segments),
            "start": round(segment.start, 3),
            "end": round(segment.end, 3),
            "text": segment.text.strip(),
            "words": words,
        }
        segments.append(seg_data)
        full_text_parts.append(segment.text.strip())

    full_text = " ".join(full_text_parts)

    transcript = {
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "duration_sec": round(info.duration, 3),
        "segment_count": len(segments),
        "segments": segments,
        "full_text": full_text,
    }

    # Write transcript to disk
    output_path = Path(output_dir) / "transcript.json"
    output_path.write_text(json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(
        f"Transcription complete: {len(segments)} segments, {len(full_text)} chars, {info.duration:.1f}s duration"
    )

    return transcript


@celery_app.task(
    name="app.workers.transcribe.transcribe_source",
    queue="transcribe",
    bind=True,
    max_retries=1,
    default_retry_delay=15,
)
def transcribe_source(self, project_id: str, source_path: str) -> dict:
    """
    Transcribe the source video for a project.

    Args:
        project_id: UUID of the project
        source_path: Path to the downloaded source video

    Returns:
        dict with transcript_path and summary stats

    Updates jobs table with granular status:
        pending -> running -> success/failed
    """
    logger.info(f"[Transcribe] Starting for project {project_id}")

    _update_job_status(project_id, "running")
    _update_project_status(project_id, "transcribing")

    output_dir = str(Path(source_path).parent)

    try:
        transcript = transcribe_audio(source_path, output_dir)

        transcript_path = str(Path(output_dir) / "transcript.json")

        result = {
            "project_id": project_id,
            "transcript_path": transcript_path,
            "language": transcript["language"],
            "duration_sec": transcript["duration_sec"],
            "segment_count": transcript["segment_count"],
            "text_length": len(transcript["full_text"]),
        }

        _update_job_status(project_id, "success")
        logger.info(
            f"[Transcribe] Complete for project {project_id}: "
            f"{result['segment_count']} segments, {result['duration_sec']}s"
        )

        return result

    except FileNotFoundError as e:
        error_msg = str(e)
        logger.error(f"[Transcribe] Failed for project {project_id}: {error_msg}")
        _update_job_status(project_id, "failed", error_message=error_msg)
        _update_project_status(project_id, "failed")
        raise

    except Exception as e:
        error_msg = f"Transcription error: {e}"
        logger.error(f"[Transcribe] Error for project {project_id}: {error_msg}")

        if self.request.retries < self.max_retries:
            _update_job_status(project_id, "retrying", error_message=error_msg)
            raise self.retry(exc=e)
        else:
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise
