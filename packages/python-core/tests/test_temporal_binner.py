"""
Tests for Temporal Binning Engine — ClipForge AI.
Validates dynamic bin count, divmod remainder allocation, sum-quota invariant,
timeline coverage, and bin-membership validation.
"""
from clipforge_core.services.temporal_binner import (
    compute_temporal_bins,
    validate_bin_membership,
)


# ============================================
# Correction 2: Dynamic Bin Count + divmod
# ============================================

def test_3_clips_from_15_min_video():
    """3 clips from a 15-min (900s) video → 2 bins, sum(quota) == 3 exactly."""
    bins = compute_temporal_bins(total_duration_sec=900.0, clip_count=3)
    total_quota = sum(b["clips_quota"] for b in bins)

    assert len(bins) == 2, f"Expected 2 bins, got {len(bins)}"
    assert total_quota == 3, f"Sum of quotas {total_quota} != requested 3"

    # divmod(3, 2) = (1, 1) → bin 1 gets 2 clips, bin 2 gets 1 clip
    assert bins[0]["clips_quota"] == 2
    assert bins[1]["clips_quota"] == 1
    print(f"  3 clips / 15 min: {len(bins)} bins, quotas={[b['clips_quota'] for b in bins]}")


def test_15_clips_from_90_min_video():
    """15 clips from a 90-min (5400s) video → 9 bins, sum(quota) == 15 exactly."""
    bins = compute_temporal_bins(total_duration_sec=5400.0, clip_count=15)
    total_quota = sum(b["clips_quota"] for b in bins)

    assert len(bins) == 9, f"Expected 9 bins, got {len(bins)}"
    assert total_quota == 15, f"Sum of quotas {total_quota} != requested 15"

    # divmod(15, 9) = (1, 6) → first 6 bins get 2, last 3 bins get 1
    for i, b in enumerate(bins):
        expected = 2 if i < 6 else 1
        assert b["clips_quota"] == expected, (
            f"Bin {b['bin_id']} has quota {b['clips_quota']}, expected {expected}"
        )
    print(f"  15 clips / 90 min: {len(bins)} bins, quotas={[b['clips_quota'] for b in bins]}")


def test_5_clips_from_54_min_video():
    """5 clips from a 54-min (3240s) video → 5 bins, 1 clip each."""
    bins = compute_temporal_bins(total_duration_sec=3240.0, clip_count=5)
    total_quota = sum(b["clips_quota"] for b in bins)

    assert len(bins) == 5, f"Expected 5 bins, got {len(bins)}"
    assert total_quota == 5, f"Sum of quotas {total_quota} != requested 5"

    for b in bins:
        assert b["clips_quota"] == 1
    print(f"  5 clips / 54 min: {len(bins)} bins, quotas={[b['clips_quota'] for b in bins]}")


def test_10_clips_from_8_min_video():
    """10 clips from an 8-min (480s) video → 1 bin with all 10 clips."""
    bins = compute_temporal_bins(total_duration_sec=480.0, clip_count=10)
    total_quota = sum(b["clips_quota"] for b in bins)

    assert len(bins) == 1, f"Expected 1 bin for short video, got {len(bins)}"
    assert total_quota == 10
    assert bins[0]["clips_quota"] == 10
    print(f"  10 clips / 8 min: {len(bins)} bins, quotas={[b['clips_quota'] for b in bins]}")


# ============================================
# Correction 4: Spread Verification
# ============================================

def test_temporal_bins_cover_full_timeline():
    """Assert even-spread bins cover ≥80% of the video timeline
    and no single bin receives a disproportionate share."""
    total_duration = 3240.0  # 54 minutes
    clip_count = 10

    bins = compute_temporal_bins(
        total_duration_sec=total_duration,
        clip_count=clip_count,
    )

    # Verify bins cover the full timeline
    assert bins[0]["start_sec"] == 0.0
    assert abs(bins[-1]["end_sec"] - total_duration) < 1.0

    # Simulate selected start_secs: midpoint of each bin × its quota
    selected_starts = []
    for b in bins:
        mid = (b["start_sec"] + b["end_sec"]) / 2
        for j in range(b["clips_quota"]):
            selected_starts.append(mid + j * 20)  # small offset for multiple clips in same bin

    # Spread coverage: max - min >= 80% of total
    spread = max(selected_starts) - min(selected_starts)
    spread_pct = spread / total_duration
    print(f"  Spread: {spread:.1f}s / {total_duration:.1f}s = {spread_pct:.1%}")
    assert spread_pct >= 0.80, f"Spread {spread_pct:.1%} is below 80% threshold"

    # Per-bin proportionality: no bin gets more than ceil(clip_count/bin_count) + 1
    max_allowed_per_bin = (clip_count // len(bins)) + 2
    for b in bins:
        assert b["clips_quota"] <= max_allowed_per_bin, (
            f"Bin {b['bin_id']} has {b['clips_quota']} clips, max allowed {max_allowed_per_bin}"
        )
        print(
            f"  Bin {b['bin_id']}: {b['start_sec']:.0f}s-{b['end_sec']:.0f}s "
            f"-> {b['clips_quota']} clips"
        )


def test_bins_with_focus_window():
    """Bins should respect time_range_start/end when provided."""
    bins = compute_temporal_bins(
        total_duration_sec=3240.0,
        clip_count=6,
        time_range_start=1200.0,  # 20 minutes
        time_range_end=2400.0,    # 40 minutes → 20 min window
    )

    assert bins[0]["start_sec"] == 1200.0
    assert abs(bins[-1]["end_sec"] - 2400.0) < 1.0
    total_quota = sum(b["clips_quota"] for b in bins)
    assert total_quota == 6
    print(f"  Focus window 20:00–40:00: {len(bins)} bins, quotas={[b['clips_quota'] for b in bins]}")


# ============================================
# Bin-Membership Validation
# ============================================

def test_bin_membership_valid_candidates():
    """All candidates within their bins should pass validation."""
    bins = compute_temporal_bins(total_duration_sec=3000.0, clip_count=5)

    candidates = []
    for b in bins:
        mid = (b["start_sec"] + b["end_sec"]) / 2
        candidates.append({"start_sec": mid, "end_sec": mid + 40})

    valid, violations = validate_bin_membership(candidates, bins)
    assert len(valid) == 5
    assert len(violations) == 0


def test_bin_membership_violation_is_detected():
    """A candidate outside all bins with no remaining quota should be discarded."""
    bins = [
        {"bin_id": 1, "start_sec": 0.0, "end_sec": 600.0, "clips_quota": 1},
        {"bin_id": 2, "start_sec": 600.0, "end_sec": 1200.0, "clips_quota": 1},
    ]

    candidates = [
        {"start_sec": 300.0, "end_sec": 340.0},   # bin 1 — valid
        {"start_sec": 800.0, "end_sec": 840.0},   # bin 2 — valid
        {"start_sec": 1500.0, "end_sec": 1540.0}, # outside both bins, no quota left
    ]

    valid, violations = validate_bin_membership(candidates, bins)
    assert len(valid) == 2
    assert len(violations) == 1
    assert violations[0]["start_sec"] == 1500.0
    assert violations[0].get("bin_violation") is True
    print(f"  Valid: {len(valid)}, Violations: {len(violations)}")


def test_bin_membership_reassigns_when_quota_available():
    """A candidate outside its bin should be reassigned to another bin with quota."""
    bins = [
        {"bin_id": 1, "start_sec": 0.0, "end_sec": 600.0, "clips_quota": 2},
        {"bin_id": 2, "start_sec": 600.0, "end_sec": 1200.0, "clips_quota": 1},
    ]

    candidates = [
        {"start_sec": 300.0, "end_sec": 340.0},    # bin 1
        {"start_sec": 1500.0, "end_sec": 1540.0},  # outside all bins — should reassign to bin 1 (has 1 left)
    ]

    valid, violations = validate_bin_membership(candidates, bins)
    assert len(valid) == 2
    assert len(violations) == 0
    # Second candidate should be reassigned
    assert valid[1].get("bin_reassigned") is True
    print(f"  Reassigned candidate to bin {valid[1].get('assigned_bin')}")
