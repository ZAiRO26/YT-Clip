"""
Tests for boundary-aware duration clamping in ClipForge AI.
Injects deliberately bad LLM-style candidates and proves the guard catches them.
"""
from clipforge_core.services.candidate_ranker import clamp_to_boundary


def test_clamp_to_boundary_snaps_to_sentence_end():
    """Inject a 119s clip when max=60. Assert it snaps to a sentence
    boundary, not raw start+60."""
    transcript_segments = [
        {"start": 1264.7, "end": 1270.0, "text": "So the contestant walks in"},
        {"start": 1270.0, "end": 1278.5, "text": "and starts singing this song"},
        {"start": 1278.5, "end": 1290.3, "text": "that nobody expected"},
        {"start": 1290.3, "end": 1305.0, "text": "and the judges are completely stunned"},
        {"start": 1305.0, "end": 1320.8, "text": "Samay literally falls off his chair"},
        {"start": 1320.8, "end": 1324.2, "text": "That was incredible."},
        {"start": 1324.5, "end": 1340.0, "text": "Let me tell you what I think"},
        {"start": 1340.0, "end": 1384.0, "text": "this performance was absolutely brilliant"},
    ]
    scenes = [
        {"scene_id": 1, "start_sec": 1264.0, "end_sec": 1322.0},
        {"scene_id": 2, "start_sec": 1322.0, "end_sec": 1384.0},
    ]

    start, end, method = clamp_to_boundary(
        start_sec=1264.7,
        end_sec=1384.0,  # 119.3s duration — way over 60s max
        max_length_sec=60,
        min_length_sec=20,
        transcript_segments=transcript_segments,
        scenes=scenes,
    )

    assert end - start <= 60, f"Clamped duration {end - start:.1f}s exceeds max 60s"
    # Must NOT be the raw chop at 1264.7 + 60 = 1324.7
    # Should snap to sentence end at 1324.2 (within [1319.7, 1324.7] window)
    assert method in ("sentence_boundary", "scene_boundary"), (
        f"Expected boundary snap, got '{method}'"
    )
    # 1324.2 is the sentence end "That was incredible." — closest to hard limit
    # 1322.0 is scene boundary — also valid but sentence is closer to hard limit
    assert end == 1324.2, f"Expected end at 1324.2 (sentence boundary), got {end}"


def test_clamp_to_boundary_raw_fallback_when_no_boundary(caplog):
    """When no sentence or scene boundary exists within tolerance,
    fall back to raw chop and log a warning."""
    # No segments end anywhere near start+60
    transcript_segments = [
        {"start": 100.0, "end": 200.0, "text": "One very long unbroken monologue"},
    ]
    scenes = []  # No scene cuts at all

    start, end, method = clamp_to_boundary(
        start_sec=100.0,
        end_sec=220.0,  # 120s, max=60
        max_length_sec=60,
        min_length_sec=20,
        transcript_segments=transcript_segments,
        scenes=scenes,
    )

    assert end == 160.0, f"Raw fallback should produce start+max = 160.0, got {end}"
    assert method == "raw_fallback"
    assert "raw chop fallback" in caplog.text.lower()


def test_clamp_to_boundary_extends_under_length():
    """A 10s clip when min=20 should extend to nearest sentence boundary."""
    transcript_segments = [
        {"start": 50.0, "end": 55.0, "text": "First sentence"},
        {"start": 55.0, "end": 62.0, "text": "Second sentence"},
        {"start": 62.0, "end": 71.5, "text": "Third sentence that completes the thought."},
    ]
    scenes = []

    start, end, method = clamp_to_boundary(
        start_sec=50.0,
        end_sec=60.0,  # 10s, under 20s min
        max_length_sec=60,
        min_length_sec=20,
        transcript_segments=transcript_segments,
        scenes=scenes,
    )

    assert end - start >= 20, f"Extended duration {end - start:.1f}s is still under min 20s"
    assert method in ("sentence_boundary", "scene_boundary")
    # Nearest sentence end at or after 50+20=70 is 71.5 ("Third sentence...")
    assert end == 71.5, f"Expected end at 71.5 (sentence boundary), got {end}"


def test_under_length_extension_does_not_exceed_max():
    """When min and max are close (e.g., min=55, max=60), extending
    to a sentence boundary must not push past max_length_sec."""
    transcript_segments = [
        {"start": 100.0, "end": 110.0, "text": "Short intro"},
        {"start": 110.0, "end": 170.0, "text": "Very long segment that goes way past max"},
    ]
    scenes = []

    start, end, method = clamp_to_boundary(
        start_sec=100.0,
        end_sec=105.0,  # 5s, under 55s min
        max_length_sec=60,
        min_length_sec=55,
        transcript_segments=transcript_segments,
        scenes=scenes,
    )

    assert end - start <= 60, f"Extended clip {end - start:.1f}s exceeds max 60s"
    # 170.0 is the only candidate but it exceeds upper_cap (100+60=160),
    # so raw fallback should produce min(100+55, 100+60) = 155
    assert method == "raw_fallback"
    assert end == 155.0, f"Expected end at 155.0 (raw fallback at min_length), got {end}"


def test_clamp_within_bounds_returns_none():
    """A clip that is already within [min, max] should pass through unchanged."""
    start, end, method = clamp_to_boundary(
        start_sec=100.0,
        end_sec=140.0,  # 40s, within [20, 60]
        max_length_sec=60,
        min_length_sec=20,
        transcript_segments=[],
        scenes=[],
    )

    assert start == 100.0
    assert end == 140.0
    assert method == "none"


# --- expand_to_natural_bit: widen payoff-only picks into a full bit ---

def _one_second_segments(count, pauses_after=()):
    """Back-to-back 1s segments starting at 0; a 1s silence follows each index in pauses_after."""
    segs, t = [], 0.0
    for k in range(count):
        segs.append({"start": t, "end": t + 1.0})
        t += 2.0 if k in pauses_after else 1.0
    return segs


def test_expand_short_pick_grows_mostly_backward_within_limits():
    from clipforge_core.services.candidate_ranker import expand_to_natural_bit

    segs = _one_second_segments(200)
    start, end = expand_to_natural_bit(100.0, 104.0, 20, 60, segs)
    assert 36.0 <= end - start <= 60.0  # reached preferred length (20 + 40% of 40), capped at max
    assert (100.0 - start) > (end - 104.0)  # more setup than aftermath


def test_expand_leaves_long_enough_pick_untouched():
    from clipforge_core.services.candidate_ranker import expand_to_natural_bit

    segs = _one_second_segments(200)
    assert expand_to_natural_bit(50.0, 95.0, 20, 60, segs) == (50.0, 95.0)


def test_expand_never_shrinks_pick_that_runs_past_last_segment():
    from clipforge_core.services.candidate_ranker import expand_to_natural_bit

    segs = _one_second_segments(50)  # speech ends at 50s
    start, end = expand_to_natural_bit(45.0, 58.0, 20, 60, segs)
    assert end >= 58.0 and start <= 45.0 and end - start <= 60.0
