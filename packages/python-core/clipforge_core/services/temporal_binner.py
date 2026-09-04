"""
ClipForge AI — Temporal Binning Service

Divides a video timeline into chronological bins and allocates clip quotas
to ensure even distribution across the full duration.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def compute_temporal_bins(
    total_duration_sec: float,
    clip_count: int,
    target_bin_duration: float = 600.0,
    time_range_start: float = 0.0,
    time_range_end: float | None = None,
) -> List[Dict[str, Any]]:
    """
    Divide the active timeline into chronological bins and allocate clip quotas.

    Uses divmod for exact remainder distribution: base clips per bin,
    with remainder distributed one-per-bin starting from the first bin.

    Returns a list of bin dicts:
        [{"bin_id": 1, "start_sec": 0.0, "end_sec": 648.0, "clips_quota": 2}, ...]
    """
    effective_start = time_range_start
    effective_end = time_range_end if time_range_end is not None else total_duration_sec
    effective_duration = max(1.0, effective_end - effective_start)

    # Dynamic bin count based on duration
    bin_count = max(1, round(effective_duration / target_bin_duration))

    # Exact quota allocation via divmod
    base_per_bin, remainder = divmod(clip_count, bin_count)

    bin_duration = effective_duration / bin_count
    bins = []

    for i in range(bin_count):
        bin_start = effective_start + (i * bin_duration)
        bin_end = effective_start + ((i + 1) * bin_duration)

        # Remainder clips distributed to the first N bins
        quota = base_per_bin + (1 if i < remainder else 0)

        bins.append({
            "bin_id": i + 1,
            "start_sec": round(bin_start, 2),
            "end_sec": round(bin_end, 2),
            "clips_quota": quota,
        })

    total_allocated = sum(b["clips_quota"] for b in bins)
    logger.info(
        f"[TemporalBinner] {bin_count} bins × ~{bin_duration:.0f}s, "
        f"{clip_count} clips allocated ({total_allocated} total quota)"
    )

    return bins


def format_bin_directives(bins: List[Dict[str, Any]]) -> str:
    """
    Format temporal bins into LLM prompt directives.

    Example output:
        ## TEMPORAL DISTRIBUTION REQUIREMENT
        The source video has been divided into 5 chronological acts.
        You MUST select clips distributed across these acts:
        - Act 1: 0:00 – 10:48 (select 2 clips)
        - Act 2: 10:48 – 21:36 (select 2 clips)
        ...
    """
    if not bins:
        return ""

    def _fmt_time(sec: float) -> str:
        m, s = divmod(int(sec), 60)
        return f"{m}:{s:02d}"

    lines = [
        "## TEMPORAL DISTRIBUTION REQUIREMENT",
        f"The source video has been divided into {len(bins)} chronological acts.",
        f"You MUST select clips distributed across ALL {len(bins)} acts below.",
        "EVERY act MUST have its assigned clip quota selected from within its timestamp range:",
    ]
    for b in bins:
        lines.append(
            f"- Act {b['bin_id']}: [{b['start_sec']:.1f}s - {b['end_sec']:.1f}s] "
            f"({_fmt_time(b['start_sec'])} - {_fmt_time(b['end_sec'])}) -> "
            f"Select EXACTLY {b['clips_quota']} clip with start_sec inside [{b['start_sec']:.1f}s - {b['end_sec']:.1f}s]"
        )

    return "\n".join(lines)


def validate_bin_membership(
    candidates: List[Dict[str, Any]],
    bins: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate that each candidate's start_sec falls within its expected bin range.
    Candidates are assigned to bins by checking which bin their start_sec falls in.

    Returns (valid_candidates, violations) where violations are candidates
    whose start_sec doesn't fall in any bin that still has remaining quota.
    """
    # Track remaining quota per bin
    remaining_quota = {b["bin_id"]: b["clips_quota"] for b in bins}
    valid = []
    violations = []

    for cand in candidates:
        start = cand.get("start_sec", 0.0)

        # Find which bin this candidate belongs to
        assigned_bin = None
        for b in bins:
            if b["start_sec"] <= start < b["end_sec"]:
                assigned_bin = b["bin_id"]
                break
        # Edge case: candidate at exact end of last bin
        if assigned_bin is None and bins:
            last = bins[-1]
            if abs(start - last["end_sec"]) < 1.0:
                assigned_bin = last["bin_id"]

        if assigned_bin is not None and remaining_quota.get(assigned_bin, 0) > 0:
            remaining_quota[assigned_bin] -= 1
            cand["assigned_bin"] = assigned_bin
            valid.append(cand)
        else:
            # Try to reassign to any bin that still has quota
            reassigned = False
            for b in bins:
                if remaining_quota.get(b["bin_id"], 0) > 0:
                    remaining_quota[b["bin_id"]] -= 1
                    cand["assigned_bin"] = b["bin_id"]
                    cand["bin_reassigned"] = True
                    valid.append(cand)
                    reassigned = True
                    logger.warning(
                        f"[BinValidation] Candidate at {start:.1f}s fell outside its bin "
                        f"(expected bin {assigned_bin}), reassigned to bin {b['bin_id']}"
                    )
                    break

            if not reassigned:
                cand["assigned_bin"] = assigned_bin
                cand["bin_violation"] = True
                violations.append(cand)
                logger.warning(
                    f"[BinValidation] Candidate at {start:.1f}s discarded — "
                    f"no bin has remaining quota"
                )

    return valid, violations
