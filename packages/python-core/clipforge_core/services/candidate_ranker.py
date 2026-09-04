"""
ClipForge AI — Candidate Ranking, Scene Snapping & Duration Clamping Service
Deduplicates candidate clips, snaps start/end times to nearest scene cut boundaries,
enforces min/max duration via boundary-aware clamping, and sorts by composite score.
"""
import logging
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def clamp_to_boundary(
    start_sec: float,
    end_sec: float,
    max_length_sec: float,
    min_length_sec: float,
    transcript_segments: List[Dict[str, Any]],
    scenes: List[Dict[str, Any]],
    tolerance_sec: float = 5.0,
) -> Tuple[float, float, str]:
    """
    Clamp a clip's duration to [min_length_sec, max_length_sec] by finding
    the nearest valid sentence-end or scene-cut boundary.

    Returns (clamped_start, clamped_end, clamp_method) where clamp_method
    is one of: 'none', 'sentence_boundary', 'scene_boundary', 'raw_fallback'.
    """
    duration = end_sec - start_sec

    # --- OVER-LENGTH CLAMPING ---
    if duration > max_length_sec:
        hard_limit = start_sec + max_length_sec
        search_floor = hard_limit - tolerance_sec

        # Strategy 1: Find nearest Whisper segment end at or before hard_limit
        best_sentence_end = None
        for seg in transcript_segments:
            seg_end = seg.get("end", 0.0)
            if search_floor <= seg_end <= hard_limit:
                if best_sentence_end is None or seg_end > best_sentence_end:
                    best_sentence_end = seg_end

        if best_sentence_end is not None:
            return start_sec, round(best_sentence_end, 2), "sentence_boundary"

        # Strategy 2: Find nearest scene-cut end at or before hard_limit
        best_scene_end = None
        for scene in scenes:
            scene_end = scene.get("end_sec", 0.0)
            if search_floor <= scene_end <= hard_limit:
                if best_scene_end is None or scene_end > best_scene_end:
                    best_scene_end = scene_end

        if best_scene_end is not None:
            return start_sec, round(best_scene_end, 2), "scene_boundary"

        # Strategy 3: Raw fallback — log explicitly
        logger.warning(
            f"[DurationClamp] No sentence or scene boundary found within "
            f"{tolerance_sec}s of hard limit {hard_limit:.1f}s for clip "
            f"[{start_sec:.1f}s-{end_sec:.1f}s]. Using raw chop fallback."
        )
        return start_sec, round(hard_limit, 2), "raw_fallback"

    # --- UNDER-LENGTH CLAMPING ---
    if duration < min_length_sec:
        target_end = start_sec + min_length_sec
        # Guard: never extend past max_length_sec even when fixing under-length
        upper_cap = start_sec + max_length_sec

        # Find nearest sentence end at or after target_end (capped at upper_cap)
        best_sentence_end = None
        for seg in transcript_segments:
            seg_end = seg.get("end", 0.0)
            if target_end <= seg_end <= min(target_end + tolerance_sec, upper_cap):
                if best_sentence_end is None or seg_end < best_sentence_end:
                    best_sentence_end = seg_end

        if best_sentence_end is not None:
            return start_sec, round(best_sentence_end, 2), "sentence_boundary"

        # Scene-boundary extension (capped at upper_cap)
        best_scene_end = None
        for scene in scenes:
            scene_end = scene.get("end_sec", 0.0)
            if target_end <= scene_end <= min(target_end + tolerance_sec, upper_cap):
                if best_scene_end is None or scene_end < best_scene_end:
                    best_scene_end = scene_end

        if best_scene_end is not None:
            return start_sec, round(best_scene_end, 2), "scene_boundary"

        # Raw fallback — extend to exactly min_length_sec (capped at upper_cap)
        fallback_end = min(target_end, upper_cap)
        logger.warning(
            f"[DurationClamp] No boundary found to extend under-length clip "
            f"[{start_sec:.1f}s-{end_sec:.1f}s] to {min_length_sec}s. "
            f"Using raw extension fallback."
        )
        return start_sec, round(fallback_end, 2), "raw_fallback"

    # Duration is within bounds
    return start_sec, end_sec, "none"


def snap_to_scene_boundaries(
    start_sec: float,
    end_sec: float,
    scenes: List[Dict[str, Any]],
    tolerance_sec: float = 1.2,
) -> tuple[float, float]:
    """
    Snap candidate start and end times to the nearest scene cut boundary if within tolerance.
    Prevents visually jarring cuts a fraction of a second before or after a camera transition.
    """
    snapped_start = start_sec
    snapped_end = end_sec

    for scene in scenes:
        scene_start = scene.get("start_sec", 0.0)
        scene_end = scene.get("end_sec", 0.0)

        # Check if candidate start is close to a scene start
        if abs(start_sec - scene_start) <= tolerance_sec:
            snapped_start = scene_start

        # Check if candidate end is close to a scene end
        if abs(end_sec - scene_end) <= tolerance_sec:
            snapped_end = scene_end

    return round(snapped_start, 2), round(snapped_end, 2)


def deduplicate_and_rank_candidates(
    candidates: List[Dict[str, Any]],
    scenes: List[Dict[str, Any]] | None = None,
    max_overlap_ratio: float = 0.25,
) -> List[Dict[str, Any]]:
    """
    Deduplicates candidates that overlap significantly and sorts them by composite rank:
    composite_rank = (editorial_potential * 0.5) + ((transformation_score / 100.0) * 0.5)
    """
    if not candidates:
        return []

    scenes = scenes or []

    # 1. Snap to scene boundaries if available
    processed = []
    for cand in candidates:
        c = dict(cand)
        start = float(c.get("start_sec", 0.0))
        end = float(c.get("end_sec", 0.0))

        if scenes:
            snapped_s, snapped_e = snap_to_scene_boundaries(start, end, scenes)
            c["start_sec"] = snapped_s
            c["end_sec"] = snapped_e

        # AUDIT-P1-05: Product policy prohibits virality/monetization prediction.
        # Primary candidate editorial score is editorial_potential, with graceful fallback to legacy virality_score.
        editorial_score = float(
            c.get("editorial_potential", c.get("virality_score", c.get("score", 0.5)))
        )
        transformation = float(c.get("transformation_score", 50))
        composite = (editorial_score * 0.5) + ((transformation / 100.0) * 0.5)
        c["composite_rank"] = round(composite, 3)
        processed.append(c)

    # 2. Sort by composite rank descending
    processed.sort(key=lambda x: x["composite_rank"], reverse=True)

    # 3. Deduplicate overlapping clips
    kept: List[Dict[str, Any]] = []
    for cand in processed:
        start_a = cand["start_sec"]
        end_a = cand["end_sec"]
        dur_a = max(0.1, end_a - start_a)

        overlaps = False
        for existing in kept:
            start_b = existing["start_sec"]
            end_b = existing["end_sec"]

            # Calculate intersection
            overlap_start = max(start_a, start_b)
            overlap_end = min(end_a, end_b)
            overlap_dur = max(0.0, overlap_end - overlap_start)

            if overlap_dur / dur_a > max_overlap_ratio:
                overlaps = True
                break

        if not overlaps:
            kept.append(cand)

    return kept
