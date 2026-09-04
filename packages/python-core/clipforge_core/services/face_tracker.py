"""
ClipForge AI — Active Speaker Face Tracker (MediaPipe BlazeFace + FaceMesh)

Extracts focal points over time for smart 9:16 vertical reframing.
When multiple faces are visible, identifies the active speaker by detecting
lip movement (mouth aspect ratio via FaceMesh 468-landmark model) and
cross-referencing with transcript word-level timestamps.

Single-face frames: use that face directly (fastest path).
Multi-face + speech: pick the face with the most lip movement.
Multi-face + silence: hold last known speaker position.
No faces: center-crop fallback with exponential smoothing.
"""
import logging
import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# FaceMesh landmark indices for mouth aspect ratio (MAR) computation.
# Upper lip top: 13, Lower lip bottom: 14, Left corner: 78, Right corner: 308
_LIP_TOP = 13
_LIP_BOTTOM = 14
_LIP_LEFT = 78
_LIP_RIGHT = 308


def _build_speech_intervals(transcript: Optional[Dict[str, Any]]) -> List[Tuple[float, float]]:
    """
    Extract continuous speech intervals from transcript segments.
    Each interval is (start_sec, end_sec) when someone is speaking.
    Merges overlapping/adjacent segments within 0.3s tolerance.
    """
    if not transcript or "segments" not in transcript:
        return []

    raw_intervals = []
    for seg in transcript["segments"]:
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        if end > start:
            raw_intervals.append((start, end))

    if not raw_intervals:
        return []

    # Sort and merge overlapping intervals
    raw_intervals.sort(key=lambda x: x[0])
    merged = [raw_intervals[0]]
    for start, end in raw_intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 0.3:  # merge gap tolerance
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def _is_speech_active(time_sec: float, speech_intervals: List[Tuple[float, float]]) -> bool:
    """Check if someone is speaking at a given timestamp using binary search."""
    if not speech_intervals:
        return False

    lo, hi = 0, len(speech_intervals) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end = speech_intervals[mid]
        if time_sec < start:
            hi = mid - 1
        elif time_sec > end:
            lo = mid + 1
        else:
            return True
    return False


def _compute_mouth_aspect_ratio(landmarks, face_bbox_xmin: float, face_bbox_ymin: float,
                                 face_bbox_w: float, face_bbox_h: float) -> float:
    """
    Compute Mouth Aspect Ratio (MAR) from FaceMesh landmarks.
    MAR = vertical_lip_distance / horizontal_lip_distance
    Higher MAR = mouth more open = likely speaking.
    Landmarks are in normalized [0,1] coordinates relative to the face crop.
    """
    try:
        top = landmarks[_LIP_TOP]
        bottom = landmarks[_LIP_BOTTOM]
        left = landmarks[_LIP_LEFT]
        right = landmarks[_LIP_RIGHT]

        vertical = abs(bottom.y - top.y)
        horizontal = abs(right.x - left.x)

        if horizontal < 1e-6:
            return 0.0

        return vertical / horizontal
    except (IndexError, AttributeError):
        return 0.0


def _get_face_center_x(bbox) -> float:
    """Extract normalized center X from a MediaPipe bounding box."""
    return max(0.0, min(1.0, float(bbox.xmin + bbox.width / 2.0)))


def track_faces(
    video_path: str | Path,
    sample_fps: float = 3.0,
    smoothing_factor: float = 0.25,
    min_detection_confidence: float = 0.5,
    transcript: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    """
    Track the active speaker's face across the video timeline.

    When multiple faces are detected and speech is active (per transcript timestamps),
    uses FaceMesh lip-movement analysis to identify which face is speaking.
    Centers the focal point on the active speaker for accurate 9:16 vertical cropping.

    Args:
        video_path: Path to the source video file.
        sample_fps: Frame sampling rate for face detection.
        smoothing_factor: EMA smoothing for focal_x (0.0 = no change, 1.0 = instant jump).
        min_detection_confidence: Minimum confidence for BlazeFace detection.
        transcript: Optional transcript dict with word-level timestamps for speech detection.

    Returns:
        Dict with timeline, statistics, and speaker tracking metadata.
        Output contract is identical to the previous version for full backward compatibility.
    """
    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    # Build speech intervals from transcript for audio-visual correlation
    speech_intervals = _build_speech_intervals(transcript)
    has_transcript = len(speech_intervals) > 0

    # Initialize MediaPipe detectors
    face_detector = None
    face_mesh = None
    try:
        import mediapipe as mp
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
            mp_face = mp.solutions.face_detection
            face_detector = mp_face.FaceDetection(
                model_selection=1,
                min_detection_confidence=min_detection_confidence,
            )

        # Only initialize FaceMesh if we have transcript data for speaker detection
        if has_transcript and hasattr(mp.solutions, "face_mesh"):
            mp_mesh = mp.solutions.face_mesh
            face_mesh = mp_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=6,
                min_detection_confidence=0.4,
                min_tracking_confidence=0.3,
            )
            logger.info(f"[FaceTrack] Active speaker detection enabled ({len(speech_intervals)} speech intervals)")
    except Exception as e:
        logger.warning(f"MediaPipe initialization failed: {e}. Defaulting to center-crop.")
        face_detector = None

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened() or face_detector is None:
        if cap.isOpened():
            cap.release()
        logger.warning(f"Using center-crop fallback for {path.name}")
        return {
            "timeline": [],
            "average_focal_x": 0.5,
            "std_dev_focal_x": 0.0,
            "total_samples": 0,
            "faces_detected_samples": 0,
            "detection_rate": 0.0,
            "fallback_used": True,
            "speaker_tracking_used": False,
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
    speaker_tracking_activations = 0

    # Sliding window for mouth movement variance (last N frames per face position bucket)
    # We track MAR history keyed by approximate face x-position (quantized to 10% buckets)
    mar_history: Dict[int, List[float]] = {}
    _MAR_WINDOW_SIZE = 5

    frame_idx = 0
    try:
        while cap.isOpened():
            if frame_idx % frame_step == 0:
                ret, frame = cap.read()
                if not ret:
                    break

                total_samples += 1
                time_sec = round(frame_idx / video_fps, 3)

                if progress_callback and total_frames > 0 and total_samples % 10 == 0:
                    pct = min(100.0, round((frame_idx / total_frames) * 100.0, 1))
                    progress_callback(pct, f"Tracking faces & active speaker: {round(time_sec, 1)}s / {round(duration, 1)}s ({int(pct)}%)")

                # Downscale for fast BlazeFace inference
                small_frame = cv2.resize(frame, (480, 270))
                rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                results = face_detector.process(rgb_frame)

                detected = False
                target_x = current_smoothed_x
                num_faces = 0

                if results and results.detections:
                    num_faces = len(results.detections)
                    detected = True
                    faces_detected_count += 1

                    if num_faces == 1:
                        # Single face: use it directly (fastest path, no FaceMesh needed)
                        bbox = results.detections[0].location_data.relative_bounding_box
                        target_x = _get_face_center_x(bbox)

                    elif num_faces > 1 and face_mesh is not None and _is_speech_active(time_sec, speech_intervals):
                        # Multi-face + speech active: use FaceMesh lip movement to find speaker
                        speaker_x = _find_active_speaker(
                            rgb_frame, results.detections, face_mesh, mar_history, _MAR_WINDOW_SIZE
                        )
                        if speaker_x is not None:
                            target_x = speaker_x
                            speaker_tracking_activations += 1
                        else:
                            # FaceMesh couldn't determine speaker; fall back to largest face
                            target_x = _pick_largest_face(results.detections)

                    elif num_faces > 1 and face_mesh is not None and not _is_speech_active(time_sec, speech_intervals):
                        # Multi-face + silence: hold last known position (no jump)
                        target_x = current_smoothed_x

                    else:
                        # Multi-face but no FaceMesh or no transcript: largest face
                        target_x = _pick_largest_face(results.detections)

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
            else:
                ret = cap.grab()
                if not ret:
                    break

            frame_idx += 1
    finally:
        cap.release()
        face_detector.close()
        if face_mesh is not None:
            face_mesh.close()

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
        f"avg_focal_x={avg_x:.3f}, std_dev={std_dev_x:.3f}, fallback_used={fallback_used}, "
        f"speaker_tracking_activations={speaker_tracking_activations}"
    )

    if progress_callback:
        progress_callback(100.0, f"Completed face tracking across {total_samples} samples.")

    return {
        "video_duration_sec": round(duration, 3),
        "total_samples": total_samples,
        "faces_detected_samples": faces_detected_count,
        "detection_rate": round(detection_rate, 3),
        "average_focal_x": round(avg_x, 3),
        "std_dev_focal_x": round(std_dev_x, 3),
        "fallback_used": fallback_used,
        "speaker_tracking_used": speaker_tracking_activations > 0,
        "speaker_tracking_activations": speaker_tracking_activations,
        "timeline": timeline,
    }


def _pick_largest_face(detections) -> float:
    """Pick the face with the largest bounding box area. Returns normalized center_x."""
    best_x = 0.5
    max_area = 0.0
    for det in detections:
        bbox = det.location_data.relative_bounding_box
        area = bbox.width * bbox.height
        if area > max_area:
            max_area = area
            best_x = _get_face_center_x(bbox)
    return best_x


def _find_active_speaker(
    rgb_frame: np.ndarray,
    detections,
    face_mesh,
    mar_history: Dict[int, List[float]],
    window_size: int,
) -> Optional[float]:
    """
    Identify the active speaker among multiple detected faces using lip movement analysis.

    For each detected face:
    1. Run FaceMesh to extract 468 facial landmarks
    2. Compute Mouth Aspect Ratio (MAR)
    3. Track MAR variance over a sliding window
    4. The face with the highest MAR variance (most lip movement) is the active speaker

    Returns the normalized center_x of the active speaker, or None if undetermined.
    """
    face_candidates = []
    h, w = rgb_frame.shape[:2]

    for det in detections:
        bbox = det.location_data.relative_bounding_box
        center_x = _get_face_center_x(bbox)

        # Crop the face region from the frame for FaceMesh processing
        x1 = max(0, int((bbox.xmin - 0.05) * w))
        y1 = max(0, int((bbox.ymin - 0.05) * h))
        x2 = min(w, int((bbox.xmin + bbox.width + 0.05) * w))
        y2 = min(h, int((bbox.ymin + bbox.height + 0.05) * h))

        if x2 - x1 < 20 or y2 - y1 < 20:
            continue

        face_crop = rgb_frame[y1:y2, x1:x2]
        mesh_results = face_mesh.process(face_crop)

        mar = 0.0
        if mesh_results and mesh_results.multi_face_landmarks:
            # Use first detected face mesh in this crop
            landmarks = mesh_results.multi_face_landmarks[0].landmark
            mar = _compute_mouth_aspect_ratio(landmarks, bbox.xmin, bbox.ymin, bbox.width, bbox.height)

        # Quantize face position to bucket (10% increments) for history tracking
        bucket = int(center_x * 10)
        face_candidates.append((center_x, mar, bucket))

    if not face_candidates:
        return None

    # Update MAR history and compute variance for each face bucket
    best_speaker_x = None
    best_score = -1.0

    for center_x, mar, bucket in face_candidates:
        if bucket not in mar_history:
            mar_history[bucket] = []
        mar_history[bucket].append(mar)

        # Keep only last N entries
        if len(mar_history[bucket]) > window_size:
            mar_history[bucket] = mar_history[bucket][-window_size:]

        history = mar_history[bucket]

        # Score = MAR variance (lip movement) + current MAR (mouth openness)
        # Variance captures dynamic movement; current MAR captures instantaneous state
        if len(history) >= 2:
            mean_mar = sum(history) / len(history)
            mar_variance = sum((m - mean_mar) ** 2 for m in history) / len(history)
            score = mar_variance * 10.0 + mar * 2.0
        else:
            score = mar * 2.0

        if score > best_score:
            best_score = score
            best_speaker_x = center_x

    # Only return speaker if there's meaningful lip movement detected
    if best_score < 0.01:
        return None

    return best_speaker_x
