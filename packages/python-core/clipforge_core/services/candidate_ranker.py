"""
ClipForge AI — Candidate Ranking & Scene Snapping Service
Deduplicates candidate clips, snaps start/end times to nearest scene cut boundaries, and sorts by composite score.
"""
from typing import Any, Dict, List


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
    composite_rank = (virality_score * 0.5) + ((transformation_score / 100.0) * 0.5)
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

        # Compute composite rank
        virality = float(c.get("virality_score", c.get("score", 0.5)))
        transformation = float(c.get("transformation_score", 50))
        composite = (virality * 0.5) + ((transformation / 100.0) * 0.5)
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
