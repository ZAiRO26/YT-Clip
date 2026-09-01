"""
ClipForge AI — Factual Claim & Sensitivity Detector (v2)
Analyzes candidate transcript text to detect factual claims, statistics, medical/financial terms,
or controversial statements, tagging them for human editorial review per context2-upgrade.md Section 2.4.
"""
import re
from typing import Any, Dict, List

STATISTIC_PATTERN = re.compile(
    r"(\b\d+(?:\.\d+)?%|\$\d+(?:\.\d+)?|\b\d+\s*(?:million|billion|trillion|percent|users|dollars)\b)",
    re.IGNORECASE,
)
CLAIM_INDICATORS = [
    "proven to", "guaranteed", "always", "never", "cure", "secret to",
    "the reason why", "scientists discovered", "studies show", "the only way",
    "leaked", "confidential", "100% effective", "invest in", "make money"
]


def analyze_factual_claims(text: str) -> Dict[str, Any]:
    """
    Detects statistics, superlatives, and strong claims in candidate speech.
    """
    found_stats = [m.group(0) for m in STATISTIC_PATTERN.finditer(text)]
    found_indicators = [ind for ind in CLAIM_INDICATORS if re.search(r"\b" + re.escape(ind) + r"\b", text, re.IGNORECASE)]

    requires_review = bool(found_stats or found_indicators)

    flags = []
    if found_stats:
        flags.append(f"Contains numerical statistics: {', '.join(found_stats[:3])}")
    if found_indicators:
        flags.append(f"Contains strong claim triggers: {', '.join(found_indicators[:3])}")

    return {
        "requires_review": requires_review,
        "flags": flags,
        "statistics_found": found_stats,
        "claim_triggers_found": found_indicators,
    }
