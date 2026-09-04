"""
ClipForge AI — Silence Gap Detector & Voiceover Offset Engine

Analyzes Whisper word-level timestamps to detect qualifying pauses/silences (>= 3.0s)
and computes dynamic voiceover placement offsets for Hook Intros, Outro CTAs,
Explainers (gap-anchored), and Hype Reactions.
"""
from typing import Any, Dict, List


def find_silence_gaps(
    transcript_segments: List[Dict[str, Any]],
    clip_start_sec: float,
    clip_end_sec: float,
    min_gap_sec: float = 3.0,
) -> List[Dict[str, float]]:
    """
    Find silence/pause gaps of at least min_gap_sec within a clip's boundaries.
    Returns gaps with timestamps relative to the start of the clip (0.0s = clip_start_sec).
    """
    if not transcript_segments or clip_end_sec <= clip_start_sec:
        return []

    # Filter segments that overlap with [clip_start_sec, clip_end_sec]
    clip_segs = []
    for s in transcript_segments:
        start = float(s.get("start", 0.0))
        end = float(s.get("end", 0.0))
        if end > clip_start_sec and start < clip_end_sec:
            # Clamp segment bounds to clip boundaries
            c_start = max(clip_start_sec, start)
            c_end = min(clip_end_sec, end)
            clip_segs.append({"start": c_start, "end": c_end})

    gaps: List[Dict[str, float]] = []

    # If no segments at all in the clip, the entire clip is a gap
    if not clip_segs:
        gap_dur = clip_end_sec - clip_start_sec
        if gap_dur >= min_gap_sec:
            gaps.append({
                "start_offset_sec": 0.0,
                "end_offset_sec": round(gap_dur, 2),
                "duration_sec": round(gap_dur, 2),
                "absolute_start_sec": round(clip_start_sec, 2),
                "absolute_end_sec": round(clip_end_sec, 2),
            })
        return gaps

    # Sort segments chronologically
    clip_segs.sort(key=lambda x: x["start"])

    # 1. Leading silence gap before the first speaker
    leading_gap = clip_segs[0]["start"] - clip_start_sec
    if leading_gap >= min_gap_sec:
        gaps.append({
            "start_offset_sec": 0.0,
            "end_offset_sec": round(leading_gap, 2),
            "duration_sec": round(leading_gap, 2),
            "absolute_start_sec": round(clip_start_sec, 2),
            "absolute_end_sec": round(clip_segs[0]["start"], 2),
        })

    # 2. Intermediate pauses between consecutive segments
    for i in range(len(clip_segs) - 1):
        prev_end = clip_segs[i]["end"]
        next_start = clip_segs[i + 1]["start"]
        gap = next_start - prev_end
        if gap >= min_gap_sec:
            gaps.append({
                "start_offset_sec": round(prev_end - clip_start_sec, 2),
                "end_offset_sec": round(next_start - clip_start_sec, 2),
                "duration_sec": round(gap, 2),
                "absolute_start_sec": round(prev_end, 2),
                "absolute_end_sec": round(next_start, 2),
            })

    # 3. Trailing silence gap after the last speaker
    trailing_gap = clip_end_sec - clip_segs[-1]["end"]
    if trailing_gap >= min_gap_sec:
        gaps.append({
            "start_offset_sec": round(clip_segs[-1]["end"] - clip_start_sec, 2),
            "end_offset_sec": round(clip_end_sec - clip_start_sec, 2),
            "duration_sec": round(trailing_gap, 2),
            "absolute_start_sec": round(clip_segs[-1]["end"], 2),
            "absolute_end_sec": round(clip_end_sec, 2),
        })

    return gaps


def compute_voiceover_start_offset(
    style: str,
    clip_duration_sec: float,
    script_word_count: int,
    gaps: List[Dict[str, float]],
    punchline_offset_sec: float | None = None,
    speaking_rate_wps: float = 2.8,
    actual_audio_duration_sec: float | None = None,
    buffer_sec: float = 0.5,
) -> float:
    """
    Compute the start timestamp offset (in seconds from clip start)
    for placing the voiceover in audio_mixer.py.

    - hook_intro: 0.5s (begins immediately before performer dialogue)
    - outro_cta: clip_duration - actual_audio_duration - buffer_sec (two-pass exact tail-anchoring)
    - explainer: start of the first qualifying pause gap (>=3s), +0.2s padding
    - hype_reaction: content-aware punchline timestamp or 60% into the clip with overflow guard
    """
    effective_duration = (
        actual_audio_duration_sec
        if actual_audio_duration_sec is not None and actual_audio_duration_sec > 0.0
        else max(1.2, script_word_count / speaking_rate_wps)
    )

    if style == "hook_intro":
        return 0.5

    elif style == "outro_cta":
        # Two-pass tail anchoring: guaranteed to finish buffer_sec before clip ends
        offset = clip_duration_sec - effective_duration - buffer_sec
        return round(max(0.5, offset), 2)

    elif style == "explainer":
        # Anchor at the start of the first gap of >= 3 seconds
        if gaps:
            return round(gaps[0]["start_offset_sec"] + 0.2, 2)
        # Fallback if no gap
        return 0.5

    elif style == "hype_reaction":
        max_safe = clip_duration_sec - effective_duration - buffer_sec
        if punchline_offset_sec is not None and 0.0 <= punchline_offset_sec <= clip_duration_sec:
            return round(max(0.5, min(punchline_offset_sec, max_safe)), 2)
        # Default hype reaction overlay point: ~60% through clip, with overflow guard
        default_pt = clip_duration_sec * 0.60
        return round(max(0.5, min(default_pt, max_safe)), 2)

    return 0.5

