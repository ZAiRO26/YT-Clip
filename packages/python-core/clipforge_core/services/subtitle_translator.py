"""
ClipForge AI — Subtitle Translator Service
Contextual translation of non-English dialogue into pure, punchy English for Shorts/Reels with word-level karaoke synchronization.
"""
import asyncio
import json
import logging
from typing import Any, Dict, List

from clipforge_core.services.llm_client import llm_client
from clipforge_core.services.caption_renderer import sanitize_word

logger = logging.getLogger(__name__)

def _group_short_segments(
    segments: List[Dict[str, Any]],
    min_duration_sec: float = 2.5,
    max_gap_sec: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Merge consecutive short segments into phrases of at least min_duration_sec.

    Whisper often emits sub-second segments. A translated line squeezed into one of
    those flashes by unreadably, so translate and time whole phrases instead.
    """
    groups: List[List[Dict[str, Any]]] = []
    for seg in segments:
        cur = groups[-1] if groups else None
        if (
            cur
            and seg.get("start", 0.0) - cur[-1].get("end", 0.0) <= max_gap_sec
            and cur[-1].get("end", 0.0) - cur[0].get("start", 0.0) < min_duration_sec
        ):
            cur.append(seg)
        else:
            groups.append([seg])
    return [
        {
            "start": g[0].get("start", 0.0),
            "end": g[-1].get("end", 0.0),
            "text": " ".join(x.get("text", "").strip() for x in g),
            "words": [w for x in g for w in x.get("words", [])],
        }
        for g in groups
    ]


async def _translate_segments_async(
    segments: List[Dict[str, Any]],
    context_title: str = "",
) -> List[Dict[str, Any]]:
    if not segments:
        return []

    segments = _group_short_segments(segments)
    llm_input = [{"id": i, "text": s.get("text", "")} for i, s in enumerate(segments)]

    prompt = f"""You are an elite subtitle translator for viral YouTube Shorts and Instagram Reels.
Translate these dialogue segments into concise, punchy, pure English subtitles.
Rules:
1. Translate fully into natural, conversational English. Never leave Hindi or foreign words (e.g. 'haan' -> 'yes/yeah', 'pata chala' -> 'found out', 'socha' -> 'thought', 'bhai' -> 'bro/man').
2. Automatically correct phonetic transcription artifacts and slang.
3. Keep lines short, witty, and perfectly matching the speaker's emotional delivery.
4. Return ONLY a valid JSON object with key 'translations': a list of objects with 'id' (int) and 'english' (str).

Context: Clip "{context_title}".
Segments to translate:
{json.dumps(llm_input, indent=2)}
"""

    try:
        res = await llm_client.complete_json(
            prompt,
            "You are a professional subtitle translator translating comedy to natural English.",
            max_tokens=4096,
        )
        translations = res.get("translations", [])
        trans_map = {t["id"]: t["english"] for t in translations if "id" in t and "english" in t}
    except Exception as e:
        logger.warning(f"LLM translation failed, falling back to sanitized transcript: {e}")
        trans_map = {}

    translated_segments = []
    for i, seg in enumerate(segments):
        eng = trans_map.get(i, seg.get("text", ""))
        words = eng.strip().split()
        if not words:
            continue

        s_start = seg.get("start", 0.0)
        s_end = seg.get("end", s_start + 1.0)
        dur = max(0.3, s_end - s_start)

        total_chars = max(1, sum(len(w) for w in words))
        curr_t = s_start
        seg_words = []
        for w in words:
            clean_w = sanitize_word(w)
            w_dur = (len(clean_w) / total_chars) * dur
            seg_words.append({
                "word": clean_w.upper(),
                "start": round(curr_t, 3),
                "end": round(curr_t + w_dur, 3),
            })
            curr_t += w_dur

        translated_segments.append({
            "id": i,
            "start": round(s_start, 3),
            "end": round(s_end, 3),
            "text": eng,
            "words": seg_words,
        })

    return translated_segments


def translate_segments_to_english(
    segments: List[Dict[str, Any]],
    context_title: str = "",
) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for Celery workers and synchronous pipelines.
    Translates dialogue segments to pure English with proportional word timestamps.
    """
    if not segments:
        return []
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If inside an existing async loop, use a dedicated thread/future
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, _translate_segments_async(segments, context_title)).result(timeout=60)
        else:
            return asyncio.run(_translate_segments_async(segments, context_title))
    except Exception as e:
        logger.error(f"Error in translate_segments_to_english: {e}")
        # Fallback to sanitized segments with original timings
        fallback = []
        for s in segments:
            words = []
            for w in s.get("words", []):
                words.append({
                    "word": sanitize_word(w.get("word", "")).upper(),
                    "start": w.get("start", 0.0),
                    "end": w.get("end", 0.0),
                })
            fallback.append({
                "id": s.get("id", 0),
                "start": s.get("start", 0.0),
                "end": s.get("end", 0.0),
                "text": s.get("text", ""),
                "words": words,
            })
        return fallback
