"""
ClipForge AI — Asset Retention & Temp Media Cleanup Service (v2)
Cleans temporary processing artifacts while preserving final rendered clips, thumbnails, and render manifests.
"""
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from clipforge_core.config import settings

logger = logging.getLogger(__name__)


def cleanup_project_temp_files(
    project_id: str,
    max_age_hours: float = 24.0,
    keep_source: bool = True,
) -> Dict[str, Any]:
    """
    Cleans intermediate audio/video cuts, subtitle drafts, and temporary synthesis files.
    """
    project_dir = Path(settings.MEDIA_DIR) / project_id
    if not project_dir.exists():
        return {"project_id": project_id, "deleted_count": 0, "freed_bytes": 0}

    now = time.time()
    max_age_seconds = max_age_hours * 3600.0
    deleted_files: List[str] = []
    freed_bytes = 0

    # Patterns of temporary artifacts to purge
    temp_patterns = [
        "*.tmp",
        "*.part",
        "vo_*.mp3",
        "music_*.aac",
        "mixed_*.aac",
        "*_captions.ass",
    ]

    for pattern in temp_patterns:
        for p in project_dir.glob(pattern):
            try:
                stat = p.stat()
                if (now - stat.st_mtime) >= max_age_seconds:
                    size = stat.st_size
                    p.unlink(missing_ok=True)
                    deleted_files.append(p.name)
                    freed_bytes += size
            except Exception as e:
                logger.warning(f"[Cleanup] Could not delete {p.name}: {e}")

    # Check clips directory for unreferenced temporary renders
    clips_dir = project_dir / "clips"
    if clips_dir.exists():
        for pattern in ["*.tmp", "vo_*.mp3", "music_*.aac", "mixed_*.aac", "*_captions.ass"]:
            for p in clips_dir.glob(pattern):
                try:
                    stat = p.stat()
                    if (now - stat.st_mtime) >= max_age_seconds:
                        size = stat.st_size
                        p.unlink(missing_ok=True)
                        deleted_files.append(f"clips/{p.name}")
                        freed_bytes += size
                except Exception as e:
                    logger.warning(f"[Cleanup] Could not delete {p.name}: {e}")

    logger.info(f"[Cleanup] Purged {len(deleted_files)} temp files for project {project_id} ({freed_bytes / (1024*1024):.2f} MB freed)")
    return {
        "project_id": project_id,
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files,
        "freed_mb": round(freed_bytes / (1024 * 1024), 2),
    }
