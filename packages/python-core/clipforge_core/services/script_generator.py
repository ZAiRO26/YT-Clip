"""
ClipForge AI — AI Voiceover Script Generator

Generates editorial voiceover commentary grounded strictly in the clip's transcript,
enforces Kokoro-calibrated word count budgets per style, validates groundedness,
and computes dynamic audio placement offsets.
"""
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from clipforge_core.services.gap_detector import compute_voiceover_start_offset, find_silence_gaps
from clipforge_core.services.llm_client import llm_client

logger = logging.getLogger(__name__)

# Hard word count limits calibrated to Kokoro's speaking rate (~2.8 words/sec)
STYLE_WORD_BUDGETS = {
    "hook_intro": {"min_words": 6, "max_words": 9, "target_desc": "first 3 seconds before dialogue"},
    "outro_cta": {"min_words": 8, "max_words": 11, "target_desc": "final 3-4 seconds CTA"},
    "explainer": {"min_words": 15, "max_words": 20, "target_desc": "placed over silence gap"},
    "hype_reaction": {"min_words": 12, "max_words": 16, "target_desc": "reaction overlay"},
}

# Emotion and dramatic reaction claims to audit against transcript text
DRAMATIC_CLAIM_WORDS = {
    "shocked", "shocking", "furious", "outraged", "hated", "crying", "wept",
    "disgusted", "terrified", "hysterical", "cheated", "betrayed", "insulted",
    "devastated", "heartbroken", "screaming", "panicked", "humiliated"
}


def enforce_word_count(script: str, style: str) -> Tuple[str, int]:
    """
    Enforce hard word count limits for the given style.
    If the text exceeds max_words, cleanly truncates at the boundary.
    """
    cleaned = re.sub(r'\s+', ' ', script.strip())
    words = cleaned.split()
    budget = STYLE_WORD_BUDGETS.get(style, {"min_words": 6, "max_words": 15})
    max_words = budget["max_words"]

    if len(words) <= max_words:
        return cleaned, len(words)

    # Truncate to max_words
    truncated_words = words[:max_words]
    truncated_text = " ".join(truncated_words)

    # Clean up punctuation at cut
    if not truncated_text.endswith((".", "!", "?", "…")):
        # If there's an earlier punctuation mark near the end, stop there
        last_punct = max(
            truncated_text.rfind("."),
            truncated_text.rfind("!"),
            truncated_text.rfind("?"),
        )
        if last_punct > len(truncated_text) * 0.6:
            truncated_text = truncated_text[:last_punct + 1]
            return truncated_text, len(truncated_text.split())
        truncated_text += "..."

    return truncated_text, len(truncated_text.split())


def check_groundedness(script: str, transcript_text: str) -> Dict[str, Any]:
    """
    Verify that dramatic emotional claims in the script are grounded
    in words or dialogue actually present in the transcript snippet.
    """
    script_lower = script.lower()
    transcript_lower = transcript_text.lower()

    flagged_claims = []
    for word in DRAMATIC_CLAIM_WORDS:
        # Check if the dramatic word appears in script
        if re.search(r'\b' + re.escape(word) + r'\b', script_lower):
            # Check if root or word appears in transcript
            root = word[:4]  # e.g., 'furi', 'shoc', 'hate'
            if root not in transcript_lower:
                flagged_claims.append(word)

    if flagged_claims:
        return {
            "has_unverified_claim": True,
            "flagged_words": flagged_claims,
            "warning": (
                f"Script contains reaction claims not detected in the transcript: "
                f"'{', '.join(flagged_claims)}'. Please verify accuracy."
            ),
        }

    return {
        "has_unverified_claim": False,
        "flagged_words": [],
        "warning": None,
    }


async def generate_voiceover_script(
    clip_title: str,
    transcript_snippet: str,
    style: str = "hook_intro",
    clip_duration_sec: float = 30.0,
    clip_start_sec: float = 0.0,
    transcript_segments: List[Dict[str, Any]] | None = None,
    speaking_rate_wps: float = 2.8,
    output_audio_path: str | Path | None = None,
) -> Dict[str, Any]:
    """
    Generate an AI voiceover script tailored to a clip and style.
    Enforces Kokoro speaking rate word bounds, audits for unverified dramatic claims,
    detects content-aware punchline beats, and probes actual Kokoro audio duration (two-pass).
    """
    if style not in STYLE_WORD_BUDGETS:
        style = "hook_intro"

    budget = STYLE_WORD_BUDGETS[style]
    min_w = budget["min_words"]
    max_w = budget["max_words"]

    # Detect gaps if segments provided
    gaps = []
    if transcript_segments:
        gaps = find_silence_gaps(
            transcript_segments=transcript_segments,
            clip_start_sec=clip_start_sec,
            clip_end_sec=clip_start_sec + clip_duration_sec,
            min_gap_sec=3.0,
        )

    # Style-specific prompt guidelines
    style_guidance = {
        "hook_intro": (
            "Write a punchy opening hook introducing what the viewer is about to see. "
            f"LENGTH: EXACTLY {min_w} to {max_w} words. Must take under 3 seconds to speak."
        ),
        "outro_cta": (
            "Write a compelling closing call-to-action asking viewers their opinion on what happened. "
            f"LENGTH: EXACTLY {min_w} to {max_w} words. Must take under 3.5 seconds to speak."
        ),
        "explainer": (
            "Provide helpful editorial context explaining the background of what is happening. "
            f"LENGTH: EXACTLY {min_w} to {max_w} words."
        ),
        "hype_reaction": (
            "Provide an energetic reaction to the punchline or performance climax. "
            f"LENGTH: EXACTLY {min_w} to {max_w} words."
        ),
    }[style]

    system_prompt = (
        "You are an expert short-form video editor and scriptwriter. "
        "You create concise voiceover commentary for TikTok, YouTube Shorts, and Instagram Reels.\n\n"
        "STRICT GROUNDEDNESS DIRECTIVE:\n"
        "You must ONLY reference words, actions, and reactions explicitly present in the provided "
        "transcript snippet. Never invent drama, emotions, or quote people saying things not present in the text.\n\n"
        f"STRICT WORD COUNT LIMIT: The script MUST be between {min_w} and {max_w} words total. "
        f"Do NOT generate fewer than {min_w} words or more than {max_w} words.\n\n"
        "EDITORIAL STYLE DIRECTIVE:\n"
        "Write natural, standalone viewer-facing commentary. "
        "Never repeat internal codes, episode numbers, or filenames (e.g., do NOT say 'latent e5' or 'clip 1')."
    )

    user_prompt = f"""## CLIP TRANSCRIPT (GROUND TRUTH)
{transcript_snippet if transcript_snippet.strip() else "(Visual performance - no spoken dialogue)"}

## TARGET STYLE & AUDIENCE
- Target Style: {style.replace('_', ' ').title()}
- Word Count: EXACTLY {min_w} to {max_w} words ({budget['target_desc']})

## INSTRUCTIONS
- Write natural, compelling short-form viewer copy.
- Ground every statement strictly in the spoken dialogue above.
- Do NOT include internal episode or project codes.
{style_guidance}

Return a JSON object:
{{
  "script": "Your drafted voiceover script here",
  "rationale": "Brief note explaining why this text fits the moment"
}}"""

    try:
        response = await llm_client.complete_json(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.3,
        )
        raw_script = response.get("script", "").strip()
        if not raw_script:
            raise ValueError("Empty script returned from LLM")
    except Exception as e:
        logger.error(f"Script generation LLM error: {e}")
        # Fallback default templates (clean, viewer-facing copy with zero internal metadata)
        if style == "hook_intro":
            raw_script = "Wait until you see what happens next in this clip!"
        elif style == "outro_cta":
            raw_script = "Did the judges score this fairly? Tell us below."
        elif style == "explainer":
            raw_script = "Here is the essential context behind what happens in this scene."
        else:
            raw_script = "You have got to see this reaction to believe it!"

    # Enforce word count server-side (truncate or clean if over budget)
    final_script, word_count = enforce_word_count(raw_script, style)

    # Check groundedness against transcript
    groundedness = check_groundedness(final_script, transcript_snippet)

    # Content-aware punchline detection for Hype Reaction
    punchline_offset = None
    detected_punchline_text = None
    detected_punchline_sec = None
    if transcript_segments:
        candidates_punchlines = []
        for s in transcript_segments:
            s_start = float(s.get("start", 0.0))
            s_end = float(s.get("end", 0.0))
            if s_end > clip_start_sec and s_start < clip_start_sec + clip_duration_sec:
                s_text = s.get("text", "").strip()
                rel_end = s_end - clip_start_sec
                if ("?" in s_text or "!" in s_text) and rel_end < clip_duration_sec - 3.0:
                    candidates_punchlines.append((rel_end, s_end, s_text))

        # Prefer punchline occurring in the climax window (30% to 75% of clip duration)
        climax_min = clip_duration_sec * 0.30
        climax_max = clip_duration_sec * 0.75
        climax_beats = [c for c in candidates_punchlines if climax_min <= c[0] <= climax_max]

        chosen = climax_beats[-1] if climax_beats else (candidates_punchlines[-1] if candidates_punchlines else None)
        if chosen:
            rel_end, s_end, s_text = chosen
            # Place 0.2s after punchline ends so voiceover does not speak over punchline words
            punchline_offset = round(rel_end + 0.2, 2)
            detected_punchline_sec = round(s_end, 2)
            detected_punchline_text = s_text

    # Two-pass actual Kokoro audio duration probe (if local ONNX engine is available)
    actual_audio_duration = None
    try:
        from clipforge_core.services.tts_service import get_kokoro_engine, resolve_voice_id
        kokoro = get_kokoro_engine()
        samples, sr = kokoro.create(
            text=final_script,
            voice=resolve_voice_id("af_bella"),
            speed=1.0,
            lang="en-us",
        )
        actual_audio_duration = round(len(samples) / float(sr), 2)
        if output_audio_path:
            import soundfile as sf
            out_p = Path(output_audio_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(out_p), samples, sr)
    except Exception as e:
        logger.debug(f"[ScriptGenerator] Direct Kokoro duration probe skipped: {e}")

    # Compute start offset using real synthesized duration (two-pass)
    start_offset = compute_voiceover_start_offset(
        style=style,
        clip_duration_sec=clip_duration_sec,
        script_word_count=word_count,
        gaps=gaps,
        punchline_offset_sec=punchline_offset,
        speaking_rate_wps=speaking_rate_wps,
        actual_audio_duration_sec=actual_audio_duration,
        buffer_sec=0.5,
    )

    effective_duration_sec = (
        actual_audio_duration
        if actual_audio_duration is not None
        else round(word_count / speaking_rate_wps, 2)
    )

    return {
        "style": style,
        "script": final_script,
        "word_count": word_count,
        "min_words": min_w,
        "max_words": max_w,
        "estimated_duration_sec": effective_duration_sec,
        "actual_audio_duration_sec": actual_audio_duration,
        "is_two_pass_measured": actual_audio_duration is not None,
        "start_offset_sec": start_offset,
        "detected_punchline_sec": detected_punchline_sec,
        "detected_punchline_text": detected_punchline_text,
        "has_qualifying_gap": len(gaps) > 0,
        "gaps": gaps,
        "has_unverified_claim": groundedness["has_unverified_claim"],
        "flagged_words": groundedness["flagged_words"],
        "warning": groundedness["warning"],
        "source_transcript": transcript_snippet,
    }
