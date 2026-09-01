"""
ClipForge AI — Advanced Caption & Subtitle Generator (ASS/SSA)
Generates deterministic subtitle files for 4 presets with word-level karaoke synchronization.

Presets:
1. bold_karaoke: Dynamic word-by-word yellow highlight with thick black border (TikTok/Reels style).
2. minimal: Modern clean white typography with subtle shadow.
3. clean_subtitle: Standard centered subtitle with dark background box.
4. none: Disabled captions.
"""
from pathlib import Path
from typing import Any, Dict, List


def format_ass_timestamp(seconds: float) -> str:
    """Format seconds to ASS timestamp (H:MM:SS.cs)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def get_ass_header(style_preset: str = "bold_karaoke", play_res_x: int = 1080, play_res_y: int = 1920) -> str:
    """Generate ASS script header with styling definitions."""
    if style_preset == "bold_karaoke":
        # Font: Arial/Montserrat, Font size 72, Bold, Yellow highlight, Primary White, Outline Black (width 4)
        style_def = (
            "Style: Default,Arial,68,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,4.5,1,2,60,60,340,1"
        )
    elif style_preset == "minimal":
        # Minimalist white typography with clean drop shadow
        style_def = (
            "Style: Default,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,&H60000000,"
            "0,0,0,0,100,100,0,0,1,2.0,2,2,80,80,260,1"
        )
    elif style_preset == "clean_subtitle":
        # Classic box background subtitle
        style_def = (
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,"
            "0,0,0,0,100,100,0,0,3,0,0,2,80,80,240,1"
        )
    else:  # none or default fallback
        style_def = (
            "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
            "0,0,0,0,100,100,0,0,1,2,0,2,60,60,200,1"
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
) -> Path:
    """
    Generate an ASS subtitle file tailored to the exact clip time range with word-level karaoke timing.
    """
    out_path = Path(output_ass_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if style_preset == "none":
        # Write empty ASS file
        out_path.write_text(get_ass_header("none"), encoding="utf-8")
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
                    clip_words.append({
                        "word": w.get("word", "").strip(),
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
                            clip_words.append({
                                "word": rw,
                                "start": max(0.0, ws - clip_start_sec),
                                "end": max(0.0, we - clip_start_sec),
                            })

    events: List[str] = []

    # Group into short digestible chunks (2 to 4 words per line for mobile 9:16)
    i = 0
    while i < len(clip_words):
        chunk = clip_words[i : i + words_per_line]
        if not chunk:
            break

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
            for w in chunk:
                w_dur_centi = max(10, int(round((w["end"] - w["start"]) * 100)))
                clean_word = w["word"].upper()
                text_parts.append(f"{{\\k{w_dur_centi}}}{clean_word}")
            ass_text = " ".join(text_parts)
        else:
            ass_text = " ".join(w["word"] for w in chunk)

        events.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{ass_text}")
        i += words_per_line

    full_ass = get_ass_header(style_preset) + "\n".join(events) + "\n"
    out_path.write_text(full_ass, encoding="utf-8")
    return out_path
