"""
ClipForge AI — Advanced Caption & Subtitle Generator (ASS/SSA)
Generates deterministic subtitle files for 4 presets with word-level karaoke synchronization.

Presets:
1. bold_karaoke: Dynamic word-by-word yellow highlight with thick black border (TikTok/Reels style).
2. minimal: Modern clean white typography with subtle shadow.
3. clean_subtitle: Standard centered subtitle with dark background box.
4. none: Disabled captions.
"""
import json
from pathlib import Path
import re
from typing import Any, Dict, List

_URDU_TRANSLIT_MAP: Dict[str, str] | None = None

_URDU_CHAR_MAP: Dict[str, str] = {
    '\u0627': 'a', '\u0622': 'aa', '\u0628': 'b', '\u067e': 'p', '\u062a': 't', '\u0679': 't', '\u062b': 's',
    '\u062c': 'j', '\u0686': 'ch', '\u062d': 'h', '\u062e': 'kh', '\u062f': 'd', '\u0688': 'd', '\u0630': 'z',
    '\u0631': 'r', '\u0691': 'r', '\u0632': 'z', '\u0698': 'zh', '\u0633': 's', '\u0634': 'sh', '\u0635': 's',
    '\u0636': 'z', '\u0637': 't', '\u0638': 'z', '\u0639': 'a', '\u063a': 'gh', '\u0641': 'f', '\u0642': 'q',
    '\u06a9': 'k', '\u06af': 'g', '\u0644': 'l', '\u0645': 'm', '\u0646': 'n', '\u06ba': 'n', '\u0648': 'o',
    '\u06c1': 'h', '\u06be': 'h', '\u0621': '', '\u06cc': 'i', '\u06d2': 'e', '\u0626': 'i', '\u0624': 'o',
    '\u06c2': 'ah', '\u06c3': 't', '\u06d3': 'e',
}


def _is_perso_arabic(ch: str) -> bool:
    return (
        '\u0600' <= ch <= '\u06FF'
        or '\u0750' <= ch <= '\u077F'
        or '\u08A0' <= ch <= '\u08FF'
        or '\uFB50' <= ch <= '\uFDFF'
        or '\uFE70' <= ch <= '\uFEFF'
    )


def _get_translit_map() -> Dict[str, str]:
    global _URDU_TRANSLIT_MAP
    if _URDU_TRANSLIT_MAP is None:
        try:
            map_path = Path(__file__).parent / "urdu_translit_map.json"
            if map_path.exists():
                _URDU_TRANSLIT_MAP = json.loads(map_path.read_text(encoding="utf-8"))
            else:
                _URDU_TRANSLIT_MAP = {}
        except Exception:
            _URDU_TRANSLIT_MAP = {}
    return _URDU_TRANSLIT_MAP


def sanitize_word(word: str) -> str:
    """
    Sanitize word so Perso-Arabic/Urdu tokens are transliterated to clean Latin/Roman Hinglish.
    Preserves surrounding punctuation and guarantees zero disconnected right-to-left glyphs in ASS.
    Multi-tier protection:
      1. Word-level transliteration dictionary lookup (semantic accuracy)
      2. Character-level phonetic transliteration fallback (for unseen tokens)
      3. Total unicode strip of any residual Perso-Arabic glyphs
    """
    if not word:
        return ""

    if not any(_is_perso_arabic(ch) for ch in word):
        return word

    translit_map = _get_translit_map()

    # Extract leading punctuation, core token, and trailing punctuation
    m = re.match(
        r"^([^\w\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]*)"
        r"([\w\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]+)"
        r"([^\w\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]*)$",
        word,
    )
    if m:
        prefix, core, suffix = m.groups()
        # 1. Direct word lookup
        roman = translit_map.get(core)
        if roman:
            return f"{prefix}{roman}{suffix}"
        # 2. Substring lookup for pure urdu chars
        urdu_only = "".join(c for c in core if _is_perso_arabic(c))
        if urdu_only in translit_map:
            return f"{prefix}{translit_map[urdu_only]}{suffix}"
        # 3. Phonetic character-by-character fallback
        phonetic = "".join(_URDU_CHAR_MAP.get(c, c) for c in core)
        # 4. Strict guarantee: strip any remaining Arabic-range unicode
        cleaned = "".join(c for c in phonetic if not _is_perso_arabic(c))
        return f"{prefix}{cleaned}{suffix}".strip()

    if word in translit_map:
        return translit_map[word]

    # Phonetic fallback + strip
    phonetic = "".join(_URDU_CHAR_MAP.get(c, c) for c in word)
    return "".join(c for c in phonetic if not _is_perso_arabic(c))




def format_ass_timestamp(seconds: float) -> str:
    """Format seconds to ASS timestamp (H:MM:SS.cs)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def get_ass_header(
    style_preset: str = "bold_karaoke",
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    layout_mode: str = "standard",
) -> str:
    """Generate ASS script header with styling definitions."""
    margin_v = 340 if style_preset == "bold_karaoke" else (260 if style_preset == "minimal" else (240 if style_preset == "clean_subtitle" else 200))
    if layout_mode == "stacked_speaker":
        margin_v = 140

    if style_preset == "bold_karaoke":
        # Font: Arial/Montserrat, Font size 68, Bold, Yellow highlight, Primary White, Outline Black (width 4)
        style_def = (
            f"Style: Default,Arial,68,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,"
            f"-1,0,0,0,100,100,0,0,1,4.5,1,2,60,60,{margin_v},1"
        )
    elif style_preset == "minimal":
        # Minimalist white typography with clean drop shadow
        style_def = (
            f"Style: Default,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,&H60000000,"
            f"0,0,0,0,100,100,0,0,1,2.0,2,2,80,80,{margin_v},1"
        )
    elif style_preset == "clean_subtitle":
        # Classic box background subtitle
        style_def = (
            f"Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H60000000,&H60000000,"
            f"0,0,0,0,100,100,0,0,3,8,0,2,80,80,{margin_v},1"
        )
    else:  # none or default fallback
        style_def = (
            f"Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
            f"0,0,0,0,100,100,0,0,1,2,0,2,60,60,{margin_v},1"
        )

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_def}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header


def generate_ass_subtitles(
    transcript_segments: List[Dict[str, Any]],
    clip_start_sec: float,
    clip_end_sec: float,
    output_ass_path: str | Path,
    style_preset: str = "bold_karaoke",
    words_per_line: int = 4,
    layout_mode: str = "standard",
) -> Path:
    """
    Generate an ASS subtitle file tailored to the exact clip time range with word-level karaoke timing.
    """
    out_path = Path(output_ass_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if style_preset == "none":
        # Write empty ASS file
        out_path.write_text(get_ass_header("none", layout_mode=layout_mode), encoding="utf-8")
        return out_path

    # Filter words belonging to [clip_start_sec, clip_end_sec]
    clip_words: List[Dict[str, Any]] = []
    for seg in transcript_segments:
        words = seg.get("words", [])
        if words:
            for w in words:
                w_start = w.get("start", 0.0)
                w_end = w.get("end", 0.0)
                if w_end >= clip_start_sec and w_start <= clip_end_sec:
                    clean_w = sanitize_word(w.get("word", "").strip())
                    if clean_w:
                        clip_words.append({
                            "word": clean_w,
                            "start": max(0.0, w_start - clip_start_sec),
                            "end": max(0.0, w_end - clip_start_sec),
                        })
        else:
            # Fallback if no word timestamps: split segment text evenly
            seg_s = seg.get("start", 0.0)
            seg_e = seg.get("end", 0.0)
            if seg_e >= clip_start_sec and seg_s <= clip_end_sec:
                raw_words = seg.get("text", "").strip().split()
                if raw_words:
                    dur_per_word = (seg_e - seg_s) / len(raw_words)
                    for i, rw in enumerate(raw_words):
                        ws = seg_s + (i * dur_per_word)
                        we = ws + dur_per_word
                        if we >= clip_start_sec and ws <= clip_end_sec:
                            clean_w = sanitize_word(rw.strip())
                            if clean_w:
                                clip_words.append({
                                    "word": clean_w,
                                    "start": max(0.0, ws - clip_start_sec),
                                    "end": max(0.0, we - clip_start_sec),
                                })

    events: List[str] = []

    # Group into short digestible chunks (2 to 4 words per line for mobile 9:16)
    i = 0
    while i < len(clip_words):
        # End the line early at a sentence end or a speech pause so lines don't straddle them
        chunk = [clip_words[i]]
        while len(chunk) < words_per_line and i + len(chunk) < len(clip_words):
            nxt = clip_words[i + len(chunk)]
            if chunk[-1]["word"].rstrip("\"')").endswith((".", "?", "!")) or nxt["start"] - chunk[-1]["end"] > 0.7:
                break
            chunk.append(nxt)
        # Pull in a lone sentence-final word rather than flashing it as its own line
        if len(chunk) == words_per_line and i + len(chunk) < len(clip_words):
            nxt = clip_words[i + len(chunk)]
            if (
                not chunk[-1]["word"].rstrip("\"')").endswith((".", "?", "!"))
                and nxt["word"].rstrip("\"')").endswith((".", "?", "!"))
                and nxt["start"] - chunk[-1]["end"] <= 0.7
            ):
                chunk.append(nxt)

        chunk_start = chunk[0]["start"]
        chunk_end = chunk[-1]["end"]

        # Ensure minimal display duration (at least 0.4s)
        if chunk_end <= chunk_start:
            chunk_end = chunk_start + 0.5

        start_str = format_ass_timestamp(chunk_start)
        end_str = format_ass_timestamp(chunk_end)

        if style_preset == "bold_karaoke":
            # Karaoke timing tags: {\k<centiseconds>}Word
            text_parts = []
            for w_idx, w in enumerate(chunk):
                # Hold each word until the next one starts so pauses don't desync the highlight
                w_next = chunk[w_idx + 1]["start"] if w_idx + 1 < len(chunk) else w["end"]
                w_dur_centi = max(10, int(round((max(w_next, w["end"]) - w["start"]) * 100)))
                clean_word = w["word"].upper()
                text_parts.append(f"{{\\k{w_dur_centi}}}{clean_word}")
            ass_text = " ".join(text_parts)
        else:
            ass_text = " ".join(w["word"] for w in chunk)

        events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{ass_text}")
        i += len(chunk)

    full_ass = get_ass_header(style_preset, layout_mode=layout_mode) + "\n".join(events) + "\n"
    out_path.write_text(full_ass, encoding="utf-8")
    return out_path
