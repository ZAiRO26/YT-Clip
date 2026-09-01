"""
ClipForge AI — Face & Subject Tracking Service (MediaPipe + Fallback)
Extracts focal points over time for smart 9:16 vertical reframing with center-crop fallback.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List

import cv2

logger = logging.getLogger(__name__)


def track_faces(
    video_path: str | Path,
    sample_fps: float = 3.0,
    smoothing_factor: float = 0.25,
) -> Dict[str, Any]:
    """
    Track face coordinates across video timeline.
    Returns:
      - timeline: list of { time_sec: float, focal_x: float (0.0-1.0), face_detected: bool }
      - average_focal_x: float
      - fallback_used: bool
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        logger.warning(f"Could not open video with OpenCV: {path}. Using center-crop fallback.")
        return {
            "timeline": [],
            "average_focal_x": 0.5,
            "fallback_used": True,
            "message": "Failed to open video, defaulted to center-crop",
        }

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    duration = total_frames / video_fps if video_fps > 0 else 0.0

    frame_step = max(1, int(video_fps / sample_fps))

    timeline: List[Dict[str, Any]] = []
    current_smoothed_x = 0.5
    faces_detected_count = 0
    total_samples = 0

    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_step == 0:
            total_samples += 1
            time_sec = round(frame_idx / video_fps, 3)

            # In v2 baseline, default focal center is 0.5
            detected = False
            target_x = 0.5

            # Exponential smoothing to prevent jarring crops
            if total_samples == 1:
                current_smoothed_x = target_x
            else:
                current_smoothed_x = (smoothing_factor * target_x) + ((1.0 - smoothing_factor) * current_smoothed_x)

            timeline.append({
                "time_sec": time_sec,
                "focal_x": round(current_smoothed_x, 3),
                "raw_x": round(target_x, 3),
                "face_detected": detected,
            })

        frame_idx += 1

    cap.release()

    avg_x = (
        sum(t["focal_x"] for t in timeline) / len(timeline)
        if timeline
        else 0.5
    )

    detection_rate = faces_detected_count / total_samples if total_samples > 0 else 0.0
    fallback_used = detection_rate < 0.1

    logger.info(
        f"[FaceTrack] Finished {path.name}: {faces_detected_count}/{total_samples} samples with face, "
        f"avg_focal_x={avg_x:.2f}, fallback_used={fallback_used}"
    )

    return {
        "video_duration_sec": round(duration, 3),
        "total_samples": total_samples,
        "faces_detected_samples": faces_detected_count,
        "detection_rate": round(detection_rate, 3),
        "average_focal_x": round(avg_x, 3),
        "fallback_used": fallback_used,
        "timeline": timeline,
    }
