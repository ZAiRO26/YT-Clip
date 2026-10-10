"""
ClipForge AI — Celery Application Configuration (v2)

Named queue architecture per context2-upgrade.md Section 3.4:
  - ingest:     yt-dlp, local-file validation, ffprobe (concurrency=2, I/O bound)
  - analysis:   faster-whisper, PySceneDetect, MediaPipe face/subject tracking (concurrency=1)
  - llm:        candidate selection, script drafts, transformation scoring (concurrency=2, rate-limited)
  - editorial:  hook cards, callout generation, caption timings (concurrency=2)
  - render:     FFmpeg cut, composite, motion effects, audio mix, burn-in (concurrency=1-2)
  - qa:         technical QC, aspect/loudness validation, manifest output (concurrency=3)
  - default:    unrouted fallback tasks
"""
import logging
import uuid
from datetime import datetime, timezone

from celery import Celery, Task
from kombu import Exchange, Queue

from clipforge_core.config import settings

logger = logging.getLogger(__name__)

_STAGE_ORDER = ["download", "transcribe", "select", "crop", "caption"]


class PipelineTask(Task):
    """
    Safety net: if a pipeline task dies with an unhandled error, mark the project
    and its active stage as failed so the UI shows the reason and offers Retry,
    instead of leaving the project "running" forever.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        project_id = kwargs.get("project_id") or (args[0] if args else None)
        if not project_id:
            return
        from clipforge_core.database import get_sync_session
        from clipforge_core.models import Job, Project

        session = get_sync_session()
        try:
            pid = uuid.UUID(str(project_id))
            project = session.query(Project).filter(Project.id == pid).first()
            if not project or project.status in ("done", "failed"):
                return
            jobs = session.query(Job).filter(Job.project_id == pid).all()
            active = [j for j in jobs if j.status in ("running", "retrying")]
            if not active:
                pending = sorted(
                    (j for j in jobs if j.status == "pending" and j.stage in _STAGE_ORDER),
                    key=lambda j: _STAGE_ORDER.index(j.stage),
                )
                active = pending[:1]
            now = datetime.now(timezone.utc)
            for job in active:
                job.status = "failed"
                job.error_message = f"{type(exc).__name__}: {exc}"[:500]
                job.completed_at = now
                job.updated_at = now
            project.status = "failed"
            session.commit()
            logger.error(f"[Pipeline] Task {self.name} failed for project {project_id}: {exc}")
        except Exception as e:
            session.rollback()
            logger.error(f"[Pipeline] Could not record failure for project {project_id}: {e}")
        finally:
            session.close()

# Create the Celery application
celery_app = Celery(
    "clipforge",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    task_cls=PipelineTask,
)

# Define standard direct exchange
default_exchange = Exchange("clipforge", type="direct")

# Configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing — mapped to v2 named queues
    task_routes={
        "clipforge_core.workers.ingest.*": {"queue": "ingest"},
        "clipforge_core.workers.download.*": {"queue": "ingest"},
        "clipforge_core.workers.analysis.*": {"queue": "analysis"},
        "clipforge_core.workers.transcribe.*": {"queue": "analysis"},
        "clipforge_core.workers.llm.*": {"queue": "llm"},
        "clipforge_core.workers.select.*": {"queue": "llm"},
        "clipforge_core.workers.editorial.*": {"queue": "editorial"},
        "clipforge_core.workers.render.*": {"queue": "render"},
        "clipforge_core.workers.caption.*": {"queue": "render"},
        "clipforge_core.workers.thumbnail.*": {"queue": "render"},
        "clipforge_core.workers.qa.*": {"queue": "qa"},
        "clipforge_core.workers.test.*": {"queue": "default"},
    },

    # Default queue for unrouted tasks
    task_default_queue="default",

    # Queue definitions
    task_queues=(
        Queue("ingest", default_exchange, routing_key="ingest"),
        Queue("analysis", default_exchange, routing_key="analysis"),
        Queue("llm", default_exchange, routing_key="llm"),
        Queue("editorial", default_exchange, routing_key="editorial"),
        Queue("render", default_exchange, routing_key="render"),
        Queue("qa", default_exchange, routing_key="qa"),
        Queue("default", default_exchange, routing_key="default"),
    ),

    # Task execution settings
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    # Full-length videos analyse for hours; limits must sit well above that
    task_time_limit=8 * 3600,
    task_soft_time_limit=7 * 3600,
    # With acks_late, Redis re-delivers any task still unacknowledged after this long.
    # The 1h default would re-queue a long analysis while it is still running.
    broker_transport_options={"visibility_timeout": 12 * 3600},

    # Result settings
    result_expires=86400,
    result_extended=True,

    # Retry defaults
    task_default_retry_delay=30,
    task_max_retries=3,

    # Worker limits
    worker_max_tasks_per_child=50,
    worker_max_memory_per_child=512000,
)


@celery_app.task(name="clipforge_core.workers.test.noop_task")
def noop_task(payload: dict | None = None) -> dict:
    """No-op test worker task for queue connectivity verification."""
    return {
        "status": "ok",
        "message": "no-op worker task executed successfully",
        "payload": payload or {},
    }


# Auto-discover tasks
celery_app.autodiscover_tasks(["clipforge_core.workers", "clipforge_core.services"])
