"""
ClipForge AI — Ingest / Download Worker (v2)

Pipeline stage 1 (Ingest Queue):
- yt-dlp adapter for YouTube URLs with robust error handling
- Local file / directory ingestion (no lossy re-encoding)
- Automatic ffprobe extraction and validation
- Database persistence to SourceAsset and ProjectAuditEvent tables
- Granular status updates to jobs table
"""
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yt_dlp

from clipforge_core.celery_app import celery_app
from clipforge_core.config import settings
from clipforge_core.database import get_sync_session
from clipforge_core.models import Job, Project, ProjectAuditEvent, SourceAsset
from clipforge_core.services.media_probe import probe_media

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv", ".wmv", ".m4v"}


def _get_project_dir(project_id: str) -> Path:
    """Get or create the project media directory."""
    project_dir = Path(settings.MEDIA_DIR) / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _update_job_status(
    project_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update the ingest/download job status in the database."""
    session = get_sync_session()
    try:
        job = (
            session.query(Job)
            .filter(
                Job.project_id == uuid.UUID(project_id),
                Job.stage.in_(["ingest", "download"]),
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
            logger.warning(f"No ingest/download job found for project {project_id}")
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


def _record_source_asset(
    project_id: str,
    source_type: str,
    source_url: str | None,
    storage_path: str,
    probe_info: Dict[str, Any],
) -> None:
    """Persist technical probe metadata into the SourceAsset & Audit tables."""
    session = get_sync_session()
    try:
        pid = uuid.UUID(project_id)
        # Check if asset already exists
        existing = session.query(SourceAsset).filter(SourceAsset.project_id == pid).first()
        if existing:
            asset = existing
            asset.source_type = source_type
            asset.source_url = source_url
            asset.storage_path = storage_path
            asset.duration_sec = probe_info.get("duration_sec")
            asset.width = probe_info.get("width")
            asset.height = probe_info.get("height")
            asset.fps = probe_info.get("fps")
            asset.video_codec = probe_info.get("video_codec")
            asset.audio_codec = probe_info.get("audio_codec")
            asset.metadata_json = probe_info
        else:
            asset = SourceAsset(
                id=uuid.uuid4(),
                project_id=pid,
                source_type=source_type,
                source_url=source_url,
                storage_path=storage_path,
                duration_sec=probe_info.get("duration_sec"),
                width=probe_info.get("width"),
                height=probe_info.get("height"),
                fps=probe_info.get("fps"),
                video_codec=probe_info.get("video_codec"),
                audio_codec=probe_info.get("audio_codec"),
                metadata_json=probe_info,
            )
            session.add(asset)

        # Record audit event
        audit = ProjectAuditEvent(
            id=uuid.uuid4(),
            project_id=pid,
            event_type="source_ingested",
            payload={
                "source_type": source_type,
                "duration_sec": probe_info.get("duration_sec"),
                "resolution": f"{probe_info.get('width')}x{probe_info.get('height')}",
                "fps": probe_info.get("fps"),
                "has_audio": probe_info.get("has_audio"),
                "file_size_mb": probe_info.get("file_size_mb"),
            },
        )
        session.add(audit)
        session.commit()
    except Exception as e:
        logger.error(f"Failed to record source asset in database: {e}")
        session.rollback()
    finally:
        session.close()


def _download_youtube(url: str, output_path: Path) -> dict:
    """Download a YouTube video using yt-dlp."""
    ydl_opts = {
        "format": "best[ext=mp4]/bestvideo[height<=1080]+bestaudio/best",
        "outtmpl": str(output_path),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": False,
        "extract_flat": False,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                raise ValueError(f"Could not extract info from URL: {url}")

            metadata = {
                "title": info.get("title", "Unknown"),
                "duration_sec": info.get("duration", 0),
                "resolution": f"{info.get('width', '?')}x{info.get('height', '?')}",
                "uploader": info.get("uploader", "Unknown"),
                "view_count": info.get("view_count", 0),
                "upload_date": info.get("upload_date", ""),
            }

            logger.info(f"Downloading YouTube video: {metadata['title']} ({metadata['duration_sec']}s)")
            ydl.download([url])
            return metadata

    except yt_dlp.utils.DownloadError as e:
        error_str = str(e).lower()
        if "private" in error_str:
            raise ValueError(f"Video is private or requires authentication: {url}")
        elif "unavailable" in error_str or "not available" in error_str:
            raise ValueError(f"Video is unavailable or region-locked: {url}")
        elif "not a valid url" in error_str or "unsupported url" in error_str:
            raise ValueError(f"Invalid YouTube URL: {url}")
        else:
            raise ValueError(f"Download failed: {e}")


def _ingest_local_folder(folder_path: str, project_dir: Path) -> dict:
    """Ingest video file from local path."""
    source_dir = Path(folder_path)

    if not source_dir.exists():
        raise ValueError(f"Local file/folder does not exist: {folder_path}")

    if source_dir.is_file():
        if source_dir.suffix.lower() in VIDEO_EXTENSIONS:
            dest = project_dir / "source.mp4"
            shutil.copy2(str(source_dir), str(dest))
            return {
                "title": source_dir.stem,
                "source_file": str(source_dir),
                "file_size_mb": round(dest.stat().st_size / (1024 * 1024), 2),
                "file_count": 1,
            }
        else:
            raise ValueError(f"Unsupported video file type: {source_dir.suffix}")

    video_files = sorted([f for f in source_dir.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS])
    if not video_files:
        raise ValueError(f"No supported video files found in {folder_path}")

    source_file = video_files[0]
    dest = project_dir / "source.mp4"
    shutil.copy2(str(source_file), str(dest))

    return {
        "title": source_file.stem,
        "source_file": str(source_file),
        "file_size_mb": round(dest.stat().st_size / (1024 * 1024), 2),
        "file_count": len(video_files),
        "all_files": [f.name for f in video_files],
    }


@celery_app.task(
    name="clipforge_core.workers.download.download_source",
    queue="ingest",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def download_source(self, project_id: str, source_type: str, source_value: str) -> dict:
    """
    Ingest and probe source video for a project.
    Queue: ingest (aliases: download)
    """
    logger.info(f"[Ingest] Starting for project {project_id}: {source_type} = {source_value}")

    _update_job_status(project_id, "running")
    _update_project_status(project_id, "downloading")

    project_dir = _get_project_dir(project_id)
    output_path = project_dir / "source.mp4"

    try:
        if source_type == "youtube_url":
            metadata = _download_youtube(source_value, output_path)
            source_url = source_value
        elif source_type in ("local_folder", "upload"):
            metadata = _ingest_local_folder(source_value, project_dir)
            source_url = None
        else:
            raise ValueError(f"Unknown source_type: {source_type}")

        # Resolve actual output file if named differently
        if not output_path.exists():
            possible = list(project_dir.glob("source.*"))
            if possible:
                actual = possible[0]
                if actual.name != "source.mp4":
                    actual.rename(output_path)
            else:
                raise FileNotFoundError(f"Source file missing in {project_dir}")

        # Run ffprobe extraction
        probe_info = probe_media(output_path)
        metadata.update({
            "probe_duration": probe_info["duration_sec"],
            "resolution": f"{probe_info['width']}x{probe_info['height']}",
            "fps": probe_info["fps"],
            "has_audio": probe_info["has_audio"],
        })

        # Record to SourceAsset and Audit DB
        _record_source_asset(
            project_id=project_id,
            source_type=source_type,
            source_url=source_url,
            storage_path=str(output_path),
            probe_info=probe_info,
        )

        result = {
            "project_id": project_id,
            "source_path": str(output_path),
            "file_size_mb": probe_info["file_size_mb"],
            "probe": probe_info,
            "metadata": metadata,
        }

        _update_job_status(project_id, "success")
        logger.info(f"[Ingest] Successfully ingested and probed project {project_id}: {probe_info['width']}x{probe_info['height']} @ {probe_info['fps']}fps, {probe_info['duration_sec']}s")
        return result

    except ValueError as e:
        error_msg = str(e)
        logger.error(f"[Ingest] Failed for project {project_id}: {error_msg}")
        _update_job_status(project_id, "failed", error_message=error_msg)
        _update_project_status(project_id, "failed")
        raise

    except Exception as e:
        error_msg = f"Unexpected error during ingest: {e}"
        logger.error(f"[Ingest] Error for project {project_id}: {error_msg}")
        if self.request.retries < self.max_retries:
            _update_job_status(project_id, "retrying", error_message=error_msg)
            raise self.retry(exc=e)
        else:
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise
