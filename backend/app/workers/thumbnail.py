"""
ClipForge AI — Thumbnail Worker

Pipeline stage: Generate a thumbnail for a finished clip.

Uses ffmpeg to extract a representative frame from the clip (e.g. at 33% mark).
Optionally allows for text overlay generation via Pillow (for custom thumbnails).
"""
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

def generate_thumbnail(video_path: str, output_path: str, duration_sec: float | None = None) -> bool:
    """
    Generate a thumbnail from a video file using ffmpeg.
    Extracts a frame at 33% of the duration to ensure we capture action (bypassing intros/fades).
    """
    try:
        # Default to 2 seconds in if duration not provided or too short
        timestamp = "00:00:02"
        if duration_sec and duration_sec > 3:
            target_sec = int(duration_sec * 0.33)
            m, s = divmod(target_sec, 60)
            h, m = divmod(m, 60)
            timestamp = f"{h:02d}:{m:02d}:{s:02d}"

        logger.info(f"Generating thumbnail for {Path(video_path).name} at {timestamp}")

        cmd = [
            "ffmpeg",
            "-y",               # Overwrite
            "-ss", timestamp,   # Seek to timestamp
            "-i", video_path,   # Input file
            "-vframes", "1",    # Extract 1 frame
            "-q:v", "2",        # High quality JPEG
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg thumbnail extraction failed: {result.stderr}")
            return False
            
        return Path(output_path).exists()
    except Exception as e:
        logger.error(f"Thumbnail generation error: {e}")
        return False
