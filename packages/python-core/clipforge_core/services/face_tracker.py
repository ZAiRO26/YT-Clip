"""
ClipForge AI — Face & Subject Tracking Service (MediaPipe BlazeFace + Fallback)
Extracts focal points over time for smart 9:16 vertical reframing with center-crop fallback.
"""
import logging
import math
from pathlib import Path
from typing import Any, Dict, List

import cv2

logger = logging.getLogger(__name__)


def track_faces(
    video_path: str | Path,
    sample_fps: float = 3.0,
    smoothing_factor: float = 0.25,
    min_detection_confidence: float = 0.5,
) -> Dict[str, Any]:
    """
    Track face coordinates across video timeline using MediaPipe FaceDetection.
    Returns:
      - timeline: list of { time_sec: float, focal_x: float (0.0-1.0), raw_x: float, face_detected: bool }
      - average_focal_x: float
      - std_dev_focal_x: float (standard deviation of focal_x across all samples)
      - detection_rate: float
      - fallback_used: bool
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    # 1. Attempt MediaPipe initialization with graceful fallback
    detector = None
    try:
        import mediapipe as mp
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
            mp_face = mp.solutions.face_detection
            # model_selection=1 is optimized for full-body / medium-range video shots (within 5m)
            detector = mp_face.FaceDetection(
                model_selection=1,
                min_detection_confidence=min_detection_confidence,
            )
    except Exception as e:
        logger.warning(f"MediaPipe FaceDetection initialization failed: {e}. Defaulting to center-crop.")
        detector = None

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened() or detector is None:
        if cap.isOpened():
            cap.release()
        logger.warning(f"Using center-crop fallback for {path.name} (detector={detector is not None})")
        return {
            "timeline": [],
            "average_focal_x": 0.5,
            "std_dev_focal_x": 0.0,
            "total_samples": 0,
            "faces_detected_samples": 0,
            "detection_rate": 0.0,
            "fallback_used": True,
            "message": "MediaPipe unavailable or video unreadable, defaulted to center-crop",
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
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_step == 0:
                total_samples += 1
                time_sec = round(frame_idx / video_fps, 3)

                # Convert BGR (OpenCV) to RGB (MediaPipe)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = detector.process(rgb_frame)

                detected = False
                target_x = current_smoothed_x  # default to last known position

                if results and results.detections:
                    # Pick primary detection: largest face bounding box
                    best_detection = None
                    max_area = 0.0
                    for det in results.detections:
                        bbox = det.location_data.relative_bounding_box
                        area = bbox.width * bbox.height
                        if area > max_area:
                            max_area = area
                            best_detection = det

                    if best_detection is not None:
                        bbox = best_detection.location_data.relative_bounding_box
                        raw_center_x = bbox.xmin + (bbox.width / 2.0)
                        target_x = max(0.0, min(1.0, float(raw_center_x)))
                        detected = True
                        faces_detected_count += 1

                # Apply exponential moving average smoothing
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
    finally:
        cap.release()
        detector.close()

    # Calculate statistics
    avg_x = (
        sum(t["focal_x"] for t in timeline) / len(timeline)
        if timeline
        else 0.5
    )

    variance = (
        sum((t["focal_x"] - avg_x) ** 2 for t in timeline) / len(timeline)
        if timeline
        else 0.0
    )
    std_dev_x = math.sqrt(variance)

    detection_rate = faces_detected_count / total_samples if total_samples > 0 else 0.0
    fallback_used = detection_rate < 0.1

    logger.info(
        f"[FaceTrack] Finished {path.name}: {faces_detected_count}/{total_samples} samples ({detection_rate*100:.1f}%), "
        f"avg_focal_x={avg_x:.3f}, std_dev={std_dev_x:.3f}, fallback_used={fallback_used}"
    )

    return {
        "video_duration_sec": round(duration, 3),
        "total_samples": total_samples,
        "faces_detected_samples": faces_detected_count,
        "detection_rate": round(detection_rate, 3),
        "average_focal_x": round(avg_x, 3),
        "std_dev_focal_x": round(std_dev_x, 3),
        "fallback_used": fallback_used,
        "timeline": timeline,
    }

