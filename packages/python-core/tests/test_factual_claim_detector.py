from clipforge_core.services.factual_claim_detector import analyze_factual_claims


def test_analyze_factual_claims_detected():
    text = "Studies show that 85% of short-form viewers retain information better with on-screen annotations."
    res = analyze_factual_claims(text)
    assert res["requires_review"] is True
    assert len(res["statistics_found"]) > 0
    assert "85%" in res["statistics_found"]
    assert "studies show" in res["claim_triggers_found"]


def test_analyze_factual_claims_clean():
    text = "Let's explore how camera framing changes the viewer experience."
    res = analyze_factual_claims(text)
    assert res["requires_review"] is False
    assert len(res["flags"]) == 0
