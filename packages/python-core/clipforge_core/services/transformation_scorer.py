"""
ClipForge AI — Transformation Score Engine
Calculates deterministic 0–100 Transformation Score per context2-upgrade.md Section 2.4.

Pillars:
1. source_exclusivity (0–20): Shorter, focused excerpts score higher than raw unedited long blocks.
2. commentary_depth (0–25): Original voiceover, structured explanation, script thesis.
3. visual_alteration (0–20): Reframing, split-screen, motion, backgrounds, PiP.
4. narrative_structure (0–20): Hook, evidence point, key takeaway.
5. editorial_callouts (0–15): Context cards, lower-thirds, annotations, citations.
"""
from typing import Any, Dict, Literal


def calculate_transformation_score(
    clip_duration_sec: float,
    total_source_duration_sec: float,
    has_commentary: bool = True,
    editorial_template: str = "explainer",
    callout_count: int = 2,
    has_visual_reframing: bool = True,
    has_hook: bool = True,
    has_takeaway: bool = True,
) -> Dict[str, Any]:
    """
    Compute structured transformation score (0–100) and component breakdown.
    """
    # 1. Source Exclusivity (0–20)
    # Ratio of clip to total source: smaller percentage of source means more selective curation
    if total_source_duration_sec > 0:
        ratio = clip_duration_sec / total_source_duration_sec
        if ratio <= 0.05:
            score_exclusivity = 20
        elif ratio <= 0.15:
            score_exclusivity = 17
        elif ratio <= 0.30:
            score_exclusivity = 14
        elif ratio <= 0.50:
            score_exclusivity = 10
        else:
            score_exclusivity = 5
    else:
        score_exclusivity = 15

    # 2. Commentary Depth (0–25)
    # Template-based baseline + commentary flag
    template_commentary_weights = {
        "explainer": 22,
        "commentary": 25,
        "news_context": 20,
        "reaction_pip": 23,
        "quote_breakdown": 18,
        "campaign_promotion": 16,
    }
    base_commentary = template_commentary_weights.get(editorial_template, 18)
    score_commentary = base_commentary if has_commentary else 8

    # 3. Visual Alteration (0–20)
    score_visual = 0
    if has_visual_reframing:
        score_visual += 12
    if editorial_template in ("reaction_pip", "news_context", "explainer"):
        score_visual += 8
    else:
        score_visual += 5
    score_visual = min(20, score_visual)

    # 4. Narrative Structure (0–20)
    score_narrative = 0
    if has_hook:
        score_narrative += 10
    if has_takeaway:
        score_narrative += 10

    # 5. Editorial Callouts (0–15)
    score_callouts = min(15, callout_count * 5)

    total_score = score_exclusivity + score_commentary + score_visual + score_narrative + score_callouts
    total_score = max(0, min(100, total_score))

    if total_score >= 70:
        band: Literal["high", "moderate", "low"] = "high"
        description = "High original transformation (Strong editorial value-add)"
    elif total_score >= 40:
        band = "moderate"
        description = "Moderate transformation (Standard editorial workflow)"
    else:
        band = "low"
        description = "Low transformation (High reuse risk - human review required)"

    return {
        "score": total_score,
        "band": band,
        "description": description,
        "breakdown": {
            "source_exclusivity": score_exclusivity,
            "commentary_depth": score_commentary,
            "visual_alteration": score_visual,
            "narrative_structure": score_narrative,
            "editorial_callouts": score_callouts,
        },
    }
