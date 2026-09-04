"""
Unit tests for AI Voiceover Script Generator: word budgets and groundedness auditing.
"""
import pytest
from clipforge_core.services.script_generator import (
    STYLE_WORD_BUDGETS,
    check_groundedness,
    enforce_word_count,
)


def test_enforce_word_count_hook_intro_within_budget():
    """Script within 6-9 words is preserved."""
    script = "Watch this unbelievable panel reaction right now."
    final, count = enforce_word_count(script, "hook_intro")
    assert count <= 9
    assert final == script


def test_enforce_word_count_hook_intro_truncates_overshoot():
    """Script with 18 words is strictly capped to <= 9 words."""
    long_script = (
        "Here is what happens when a brand new comedian takes the stage "
        "and shocks all four judges with an outrageous opener."
    )
    assert len(long_script.split()) == 21
    final, count = enforce_word_count(long_script, "hook_intro")
    assert count <= 9
    assert count >= 6


def test_enforce_word_count_outro_cta_truncates():
    """Outro CTA with 20 words is truncated to <= 11 words."""
    long_cta = (
        "Do you agree with the judges' harsh score on this performance, "
        "or did they completely misunderstand the contestant's genius? Let us know."
    )
    final, count = enforce_word_count(long_cta, "outro_cta")
    assert count <= 11
    assert count >= 8


def test_check_groundedness_flags_unverified_emotional_claim():
    """Flags unverified emotional claim 'furious' when not in transcript."""
    script = "The judges were furious after this contestant spoke."
    transcript = "The judges smiled and asked the contestant to tell his joke."
    res = check_groundedness(script, transcript)
    assert res["has_unverified_claim"] is True
    assert "furious" in res["flagged_words"]
    assert res["warning"] is not None


def test_check_groundedness_passes_grounded_script():
    """Passes cleanly when emotional terms are backed by transcript dialogue."""
    script = "The judges were shocked by the contestant's score."
    transcript = "I am shocked that you gave this performance a zero."
    res = check_groundedness(script, transcript)
    assert res["has_unverified_claim"] is False
    assert len(res["flagged_words"]) == 0
    assert res["warning"] is None


# ---------------------------------------------------------------------------
# Regression: Generated scripts must never leak internal project metadata
# ---------------------------------------------------------------------------

# Deliberately provocative project title fragments that must never appear
# in viewer-facing voiceover scripts.
_LEAK_PROJECT_TITLE = "Latent E5"
_LEAK_FRAGMENTS = ["latent", "e5", "latent e5", "clip 1", "clip_1", "episode"]


class TestScriptNeverLeaksProjectTitle:
    """
    Permanent regression suite ensuring that voiceover scripts (both LLM-generated
    and fallback templates) never leak internal project titles, episode codes, or
    filename fragments into viewer-facing copy.

    Triggered by: the original 'latent e5' leak from fallback template
    `f"Watch what happens in this {clip_title.lower()}."` which formatted project
    title into user-visible narration.
    """

    def test_fallback_templates_do_not_contain_project_title(self):
        """All 4 fallback templates are static strings with zero format variables."""
        # Inline the exact fallback strings from script_generator.py so this test
        # breaks if someone re-introduces a format variable.
        fallback_templates = {
            "hook_intro": "Wait until you see what happens next in this clip!",
            "outro_cta": "Did the judges score this fairly? Tell us below.",
            "explainer": "Here is the essential context behind what happens in this scene.",
            "hype_reaction": "You have got to see this reaction to believe it!",
        }
        for style, template in fallback_templates.items():
            lower = template.lower()
            for fragment in _LEAK_FRAGMENTS:
                assert fragment not in lower, (
                    f"Fallback template for '{style}' contains leaked fragment '{fragment}': {template}"
                )

    @pytest.mark.parametrize("style", ["hook_intro", "outro_cta", "explainer", "hype_reaction"])
    def test_enforce_word_count_never_injects_title(self, style):
        """
        enforce_word_count only truncates — it should never inject project metadata.
        Feed it a clean script and confirm the output stays clean.
        """
        clean_script = "This is a perfectly normal viewer-facing voiceover commentary line for testing purposes."
        final, count = enforce_word_count(clean_script, style)
        lower = final.lower()
        for fragment in _LEAK_FRAGMENTS:
            assert fragment not in lower, (
                f"enforce_word_count for '{style}' injected leaked fragment '{fragment}': {final}"
            )

    def test_fallback_templates_match_source_code(self):
        """
        Guard against template drift: if someone changes the fallback strings in
        script_generator.py, this test forces them to update the regression test too.
        """
        import ast
        import inspect
        from clipforge_core.services.script_generator import generate_voiceover_script

        source = inspect.getsource(generate_voiceover_script)
        # Verify all 4 known-good fallback strings are present in the source
        expected_fragments = [
            "Wait until you see what happens next in this clip!",
            "Did the judges score this fairly? Tell us below.",
            "Here is the essential context behind what happens in this scene.",
            "You have got to see this reaction to believe it!",
        ]
        for expected in expected_fragments:
            assert expected in source, (
                f"Fallback template changed without updating regression test: '{expected}' "
                f"not found in generate_voiceover_script source. Update both the template "
                f"AND this regression test together."
            )
