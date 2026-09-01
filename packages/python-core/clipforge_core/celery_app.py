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
from celery import Celery
from kombu import Exchange, Queue

from clipforge_core.config import settings

# Create the Celery application
celery_app = Celery(
    "clipforge",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
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
        "clipforge_core.workers.crop.*": {"queue": "render"},
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
        # Backward-compatible queue aliases
        Queue("download", default_exchange, routing_key="download"),
        Queue("transcribe", default_exchange, routing_key="transcribe"),
        Queue("select", default_exchange, routing_key="select"),
        Queue("crop", default_exchange, routing_key="crop"),
        Queue("caption", default_exchange, routing_key="caption"),
    ),

    # Task execution settings
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=1800,
    task_soft_time_limit=1500,

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
