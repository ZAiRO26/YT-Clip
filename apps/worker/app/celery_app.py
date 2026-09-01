"""
ClipForge AI — Celery Worker App Entry Point
Re-exports the core Celery application instance.
"""
from clipforge_core.celery_app import celery_app

__all__ = ["celery_app"]
