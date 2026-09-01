"""
ClipForge AI — Celery Application Configuration

Queue-based worker pool per TRD section 2:
  - download:   yt-dlp wrapper (concurrency=6)
  - transcribe: faster-whisper (concurrency=2, CPU-bound)
  - select:     LLM clip selection (concurrency=3, rate-limited)
  - crop:       ClipsAI vertical reframe (concurrency=2, CPU-bound)
  - caption:    captacity burned-in captions (concurrency=2, CPU-bound)

Each worker type has its own Celery queue and independent concurrency setting.
Start a worker for a specific queue:
  celery -A app.celery_app worker -Q download -c 6 --loglevel=info
  celery -A app.celery_app worker -Q transcribe -c 2 --loglevel=info
Or run all queues in one worker for development:
  celery -A app.celery_app worker -Q download,transcribe,select,crop,caption -c 2 --loglevel=info
"""
from celery import Celery

from app.config import settings

# Create the Celery application
celery_app = Celery(
    "clipforge",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

# Configuration
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing — each stage gets its own queue
    task_routes={
        "app.workers.download.*": {"queue": "download"},
        "app.workers.transcribe.*": {"queue": "transcribe"},
        "app.workers.select.*": {"queue": "select"},
        "app.workers.crop.*": {"queue": "crop"},
        "app.workers.caption.*": {"queue": "caption"},
    },

    # Default queue for unrouted tasks
    task_default_queue="default",

    # Queue definitions with priorities
    task_queues={
        "download": {"exchange": "download", "routing_key": "download"},
        "transcribe": {"exchange": "transcribe", "routing_key": "transcribe"},
        "select": {"exchange": "select", "routing_key": "select"},
        "crop": {"exchange": "crop", "routing_key": "crop"},
        "caption": {"exchange": "caption", "routing_key": "caption"},
        "default": {"exchange": "default", "routing_key": "default"},
    },

    # Task execution settings
    task_acks_late=True,                 # Acknowledge after completion (crash safety)
    worker_prefetch_multiplier=1,        # One task at a time per worker process
    task_track_started=True,             # Track STARTED state
    task_time_limit=1800,                # 30 minute hard limit per task
    task_soft_time_limit=1500,           # 25 minute soft limit (raises SoftTimeLimitExceeded)

    # Result settings
    result_expires=86400,                # Results expire after 24 hours
    result_extended=True,                # Include task name in result

    # Retry defaults
    task_default_retry_delay=30,         # 30 seconds between retries
    task_max_retries=3,                  # Max 3 retries per task

    # Worker settings
    worker_max_tasks_per_child=50,       # Restart worker process after 50 tasks (memory leak prevention)
    worker_max_memory_per_child=512000,  # 512MB memory limit per worker process
)

# Auto-discover tasks in workers and services packages
celery_app.autodiscover_tasks(["app.workers", "app.services"])
