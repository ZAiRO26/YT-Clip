"""
ClipForge AI — Scene Detection Service (PySceneDetect)
Identifies video cuts and scene boundaries to avoid awkward mid-sentence cuts.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List

from scenedetect import ContentDetector, SceneManager, open_video

logger = logging.getLogger(__name__)


def detect_scenes(video_path: str | Path, threshold: float = 27.0) -> List[Dict[str, Any]]:
    """
    Detect cut scenes and return structured list of time boundaries.
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    logger.info(f"[SceneDetect] Analyzing scene boundaries for {path.name} (threshold={threshold})")

    video = open_video(str(path))
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))

    # Detect cut scenes
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    scenes = []
    for i, (start_time, end_time) in enumerate(scene_list):
        scenes.append({
            "scene_id": i + 1,
            "start_sec": round(start_time.get_seconds(), 3),
            "end_sec": round(end_time.get_seconds(), 3),
            "duration_sec": round((end_time - start_time).get_seconds(), 3),
            "start_frame": start_time.get_frames(),
            "end_frame": end_time.get_frames(),
        })

    # If no cut transitions found (single continuous shot), represent full video as 1 scene
    if not scenes:
        duration = video.duration.seconds
        scenes = [{
            "scene_id": 1,
            "start_sec": 0.0,
            "end_sec": round(duration, 3),
            "duration_sec": round(duration, 3),
            "start_frame": 0,
            "end_frame": video.duration.frame_num,
        }]

    logger.info(f"[SceneDetect] Found {len(scenes)} scenes in {path.name}")
    return scenes
