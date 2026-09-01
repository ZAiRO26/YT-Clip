"""
ClipForge AI — Download Worker

Pipeline stage 1: Download source video from YouTube or ingest from local folder.

Per TRD section 2 and user requirements:
- yt-dlp for YouTube URLs
- Local folder path as alternative input (copy/symlink, don't re-encode)
- Writes granular status to jobs table (download stage)
- Output: {MEDIA_DIR}/{project_id}/source.mp4

Celery queue: download (concurrency=6 in production)
"""
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp

from app.celery_app import celery_app
from app.config import settings
from app.database import get_sync_session
from app.models import Job, Project

logger = logging.getLogger(__name__)

# Supported video extensions for local folder ingestion
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
    """Update the download job status in the database."""
    session = get_sync_session()
    try:
        job = session.query(Job).filter(
            Job.project_id == uuid.UUID(project_id),
            Job.stage == "download",
        ).first()

        if job:
            job.status = status
            job.error_message = error_message
            if status == "running":
                job.started_at = datetime.now(timezone.utc)
            if status in ("success", "failed"):
                job.completed_at = datetime.now(timezone.utc)
            session.commit()
        else:
            logger.warning(f"No download job found for project {project_id}")
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


def _download_youtube(url: str, output_path: Path) -> dict:
    """
    Download a YouTube video using yt-dlp.

    Returns metadata dict with title, duration, resolution, etc.
    Raises on invalid/private/region-locked URLs per App Flow EC1.
    """
    ydl_opts = {
        "format": "best[ext=mp4]/bestvideo[height<=1080]+bestaudio/best",
        "outtmpl": str(output_path),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": False,
        "extract_flat": False,
        # Prevent downloading playlists — single video only
        "noplaylist": True,
        # Write metadata
        "writeinfojson": False,
        # Progress hooks
        "progress_hooks": [],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First, extract info without downloading to validate the URL
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

            logger.info(
                f"Downloading: {metadata['title']} "
                f"({metadata['duration_sec']}s, {metadata['resolution']})"
            )

            # Now actually download
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
    """
    Ingest video files from a local folder.

    Finds the first supported video file and copies it as source.mp4.
    For multiple videos, copies all of them (future: process each separately).

    Returns metadata dict with file info.
    """
    source_dir = Path(folder_path)

    if not source_dir.exists():
        raise ValueError(f"Local folder does not exist: {folder_path}")

    if not source_dir.is_dir():
        # It's a single file, not a folder
        if source_dir.is_file() and source_dir.suffix.lower() in VIDEO_EXTENSIONS:
            dest = project_dir / "source.mp4"
            shutil.copy2(str(source_dir), str(dest))
            file_size = dest.stat().st_size
            return {
                "title": source_dir.stem,
                "source_file": str(source_dir),
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "file_count": 1,
            }
        else:
            raise ValueError(
                f"Not a supported video file: {source_dir.suffix}. "
                f"Supported: {', '.join(VIDEO_EXTENSIONS)}"
            )

    # Find video files in the folder
    video_files = sorted([
        f for f in source_dir.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ])

    if not video_files:
        raise ValueError(
            f"No video files found in {folder_path}. "
            f"Supported formats: {', '.join(VIDEO_EXTENSIONS)}"
        )

    # For v1: use the first video file as the source
    # Copy it to the project directory as source.mp4
    source_file = video_files[0]
    dest = project_dir / "source.mp4"
    shutil.copy2(str(source_file), str(dest))

    file_size = dest.stat().st_size

    logger.info(
        f"Ingested local file: {source_file.name} "
        f"({round(file_size / (1024 * 1024), 2)} MB)"
    )

    if len(video_files) > 1:
        logger.info(
            f"Found {len(video_files)} video files in folder. "
            f"Using first file: {source_file.name}. "
            f"Additional files: {[f.name for f in video_files[1:]]}"
        )

    return {
        "title": source_file.stem,
        "source_file": str(source_file),
        "file_size_mb": round(file_size / (1024 * 1024), 2),
        "file_count": len(video_files),
        "all_files": [f.name for f in video_files],
    }


@celery_app.task(
    name="app.workers.download.download_source",
    queue="download",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def download_source(self, project_id: str, source_type: str, source_value: str) -> dict:
    """
    Download or ingest source video for a project.

    Args:
        project_id: UUID of the project
        source_type: 'youtube_url' or 'local_folder'
        source_value: The URL or folder path

    Returns:
        dict with source_path and metadata

    Updates jobs table with granular status per requirement #6:
        pending -> running -> success/failed
    """
    logger.info(f"[Download] Starting for project {project_id}: {source_type} = {source_value}")

    # Mark job as running
    _update_job_status(project_id, "running")
    _update_project_status(project_id, "downloading")

    project_dir = _get_project_dir(project_id)
    output_path = project_dir / "source.mp4"

    try:
        if source_type == "youtube_url":
            metadata = _download_youtube(source_value, output_path)
        elif source_type == "local_folder":
            metadata = _ingest_local_folder(source_value, project_dir)
        else:
            raise ValueError(f"Unknown source_type: {source_type}. Expected 'youtube_url' or 'local_folder'.")

        # Verify the output file exists
        if not output_path.exists():
            # yt-dlp might have added an extension — check for variants
            possible = list(project_dir.glob("source.*"))
            if possible:
                # Rename to source.mp4
                actual = possible[0]
                if actual.name != "source.mp4":
                    actual.rename(output_path)
            else:
                raise FileNotFoundError(f"Download completed but no output file found in {project_dir}")

        file_size = output_path.stat().st_size
        result = {
            "project_id": project_id,
            "source_path": str(output_path),
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "metadata": metadata,
        }

        # Mark job as success
        _update_job_status(project_id, "success")
        logger.info(f"[Download] Complete for project {project_id}: {result['file_size_mb']} MB")

        return result

    except ValueError as e:
        # User-facing errors (bad URL, missing files) — don't retry
        error_msg = str(e)
        logger.error(f"[Download] Failed for project {project_id}: {error_msg}")
        _update_job_status(project_id, "failed", error_message=error_msg)
        _update_project_status(project_id, "failed")
        raise

    except Exception as e:
        # Unexpected errors — retry with backoff
        error_msg = f"Unexpected error: {e}"
        logger.error(f"[Download] Error for project {project_id}: {error_msg}")

        if self.request.retries < self.max_retries:
            _update_job_status(project_id, "retrying", error_message=error_msg)
            raise self.retry(exc=e)
        else:
            _update_job_status(project_id, "failed", error_message=error_msg)
            _update_project_status(project_id, "failed")
            raise
