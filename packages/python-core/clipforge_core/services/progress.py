"""
ClipForge AI — Progress Tracking Service (v2)
Manages granular, throttled writes to the Job model for real-time UI updates.
"""
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Tuple

from clipforge_core.database import get_sync_session
from clipforge_core.models import Job

logger = logging.getLogger(__name__)

# Simple in-memory throttle cache (Process-local)
# Maps (project_id, stage) -> last_write_time
_LAST_WRITE_CACHE: Dict[Tuple[str, str], float] = {}
THROTTLE_SECONDS = 1.5


def update_job_progress(
    project_id: str,
    stage: str,
    status: str | None = None,
    percent: float | None = None,
    detail: str | None = None,
    error_message: str | None = None,
    force_write: bool = False,
) -> None:
    """
    Updates the Job's progress metrics. Throttles frequent writes unless force_write=True.
    """
    cache_key = (project_id, stage)
    now = time.time()

    if not force_write and cache_key in _LAST_WRITE_CACHE:
        if now - _LAST_WRITE_CACHE[cache_key] < THROTTLE_SECONDS:
            return  # Skip write to prevent DB spam

    session = get_sync_session()
    try:
        # We need to map "ingest" and "download" appropriately since stages might be aliased.
        stage_filter = [stage]
        if stage in ("ingest", "download"):
            stage_filter = ["ingest", "download"]
        elif stage in ("crop", "render", "caption"):
            stage_filter = ["crop", "render", "caption"]
        elif stage in ("analysis", "transcribe"):
            stage_filter = ["analysis", "transcribe"]

        jobs = (
            session.query(Job)
            .filter(
                Job.project_id == uuid.UUID(project_id),
                Job.stage.in_(stage_filter),
            )
            .all()
        )

        for job in jobs:
            if status:
                job.status = status
                if status == "running" and not job.started_at:
                    job.started_at = datetime.now(timezone.utc)
                if status in ("success", "failed"):
                    job.completed_at = datetime.now(timezone.utc)
            
            if percent is not None:
                job.progress_percent = float(percent)
            if detail is not None:
                job.progress_detail = str(detail)
            if error_message is not None:
                job.error_message = str(error_message)
                
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
            _LAST_WRITE_CACHE[cache_key] = now
    except Exception as e:
        logger.error(f"Failed to update job progress for {project_id} - {stage}: {e}")
        session.rollback()
    finally:
        session.close()
