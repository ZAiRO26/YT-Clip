from clipforge_core.services.transformation_scorer import calculate_transformation_score


def test_transformation_score_high_transformation():
    result = calculate_transformation_score(
        clip_duration_sec=30.0,
        total_source_duration_sec=600.0,  # 5% of source
        has_commentary=True,
        editorial_template="commentary",
        callout_count=3,
        has_visual_reframing=True,
        has_hook=True,
        has_takeaway=True,
    )
    assert result["score"] >= 70
    assert result["band"] == "high"
    assert "source_exclusivity" in result["breakdown"]
    assert "commentary_depth" in result["breakdown"]
    assert "visual_alteration" in result["breakdown"]
    assert "narrative_structure" in result["breakdown"]
    assert "editorial_callouts" in result["breakdown"]


def test_transformation_score_low_transformation():
    result = calculate_transformation_score(
        clip_duration_sec=550.0,
        total_source_duration_sec=600.0,  # 90% of source
        has_commentary=False,
        editorial_template="campaign_promotion",
        callout_count=0,
        has_visual_reframing=False,
        has_hook=False,
        has_takeaway=False,
    )
    assert result["score"] < 40
    assert result["band"] == "low"
