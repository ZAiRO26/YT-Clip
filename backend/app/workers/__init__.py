"""
ClipForge AI — Worker task definitions

Each module in this package corresponds to a pipeline stage.
Task auto-discovery is configured in celery_app.py.

Pipeline order: download -> transcribe -> select -> crop -> caption
"""
from app.celery_app import celery_app

# Import worker modules so Celery discovers their tasks
from app.workers import caption  # noqa: F401
from app.workers import crop  # noqa: F401
from app.workers import download  # noqa: F401
from app.workers import select  # noqa: F401
from app.workers import transcribe  # noqa: F401

# Import pipeline orchestrator task
from app.services import pipeline  # noqa: F401


@celery_app.task(name="app.workers.ping", queue="default")
def ping():
    """Test task to verify Celery + Redis connectivity."""
    return {"status": "pong", "service": "clipforge-worker"}
