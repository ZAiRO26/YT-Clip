"""
ClipForge AI — Audio Studio & Sidechain Ducking Mixer (v2)
Mixes source video audio, original voiceover narration, and ambient background music
with sidechain compression ducking and loudnorm mastering (-14.0 LUFS).
"""
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def mix_audio_tracks(
    source_video_path: str | Path,
    output_audio_path: str | Path,
    start_sec: float,
    end_sec: float,
    voiceover_path: str | Path | None = None,
    music_path: str | Path | None = None,
    voiceover_delay_sec: float = 0.5,
    music_volume_db: float = -8.0,
    source_duck_db: float = -12.0,
    voiceover_start_offset_sec: float | None = None,
) -> Dict[str, Any]:
    """
    Mixes audio streams into a mastered AAC track with sidechain ducking.
    Supports dynamic voiceover placement via voiceover_start_offset_sec.
    """
    src_vid = Path(source_video_path)
    out_audio = Path(output_audio_path)
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    duration = end_sec - start_sec

    # Dynamic Voiceover placement offset (backward compatible with voiceover_delay_sec)
    effective_offset = (
        voiceover_start_offset_sec
        if voiceover_start_offset_sec is not None
        else voiceover_delay_sec
    )
    delay_ms = int(effective_offset * 1000)

    inputs = [
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-i", str(src_vid),
    ]

    filter_complex_parts = []
    input_idx = 1

    vo_idx = None
    if voiceover_path and Path(voiceover_path).exists():
        inputs.extend(["-i", str(voiceover_path)])
        vo_idx = input_idx
        input_idx += 1

    music_idx = None
    if music_path and Path(music_path).exists():
        inputs.extend(["-stream_loop", "-1", "-i", str(music_path)])
        music_idx = input_idx
        input_idx += 1

    # Build filter graph
    if vo_idx is not None and music_idx is not None:
        # 3 streams: Source, VO, Music
        # Format VO to stereo 44.1kHz, delay, pad, and split into sidechain triggers and mix stream
        filter_complex_parts.append(
            f"[{vo_idx}:a]adelay={delay_ms}|{delay_ms},aformat=sample_rates=44100:channel_layouts=stereo,"
            f"volume=1.8,apad,asplit=3[vo_sc1][vo_sc2][vo_mix];"
        )
        filter_complex_parts.append(f"[{music_idx}:a]volume={music_volume_db}dB[bg_low];")
        filter_complex_parts.append(
            "[0:a][vo_sc1]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[ducked_src];"
            "[bg_low][vo_sc2]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=300[ducked_bg];"
            "[ducked_src][vo_mix][ducked_bg]amix=inputs=3:duration=first:dropout_transition=2:normalize=0,"
            "loudnorm=I=-14:LRA=7:TP=-1.5[aout]"
        )
    elif vo_idx is not None:
        # 2 streams: Source and VO
        # Format VO to stereo 44.1kHz, delay, pad, and split into sidechain trigger and mix stream
        filter_complex_parts.append(
            f"[{vo_idx}:a]adelay={delay_ms}|{delay_ms},aformat=sample_rates=44100:channel_layouts=stereo,"
            f"volume=1.8,apad,asplit=2[vo_sc][vo_mix];"
        )
        filter_complex_parts.append(
            "[0:a][vo_sc]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[ducked_src];"
            "[ducked_src][vo_mix]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,"
            "loudnorm=I=-14:LRA=7:TP=-1.5[aout]"
        )
    elif music_idx is not None:
        # 2 streams: Source and Music
        filter_complex_parts.append(
            f"[{music_idx}:a]volume={music_volume_db}dB[bg_low];"
            f"[0:a][bg_low]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,"
            f"loudnorm=I=-14:LRA=7:TP=-1.5[aout]"
        )
    else:
        # 1 stream: Just source normalized
        filter_complex_parts.append("[0:a]loudnorm=I=-14:LRA=7:TP=-1.5[aout]")

    filter_str = "".join(filter_complex_parts)

    def build_cmd(graph: str, output_args: list[str]) -> list[str]:
        return ["ffmpeg", "-y", *inputs, "-filter_complex", graph, "-map", "[aout]", "-t", str(duration), *output_args]

    logger.info(f"[AudioMixer] Mixing audio tracks (VO={'yes' if vo_idx else 'no'}, Music={'yes' if music_idx else 'no'})")

    # Two-pass loudnorm: single-pass (dynamic) mode lands 1.5-2.5 LU under target on short
    # mixed clips. Measure first, then apply a linear gain to hit -14 LUFS. Falls back to
    # single-pass if the measurement cannot be read.
    master = "loudnorm=I=-14:LRA=7:TP=-1.5"
    try:
        probe = subprocess.run(
            build_cmd(filter_str.replace(f"{master}[aout]", f"{master}:print_format=json[aout]"), ["-f", "null", "-"]),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120, check=True,
        )
        stats = json.loads(probe.stderr[probe.stderr.rindex("{"): probe.stderr.rindex("}") + 1])
        measured = (
            f"{master}:measured_I={stats['input_i']}:measured_LRA={stats['input_lra']}"
            f":measured_TP={stats['input_tp']}:measured_thresh={stats['input_thresh']}"
            f":offset={stats['target_offset']}:linear=true"
        )
        filter_str = filter_str.replace(f"{master}[aout]", f"{measured}[aout]")
    except Exception as e:
        logger.warning(f"[AudioMixer] Loudness measurement failed, using single-pass normalisation: {e}")

    cmd = build_cmd(filter_str, ["-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(out_audio)])
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120, check=True)

    return {
        "output_path": str(out_audio),
        "has_voiceover": vo_idx is not None,
        "has_music": music_idx is not None,
        "duration_sec": duration,
    }
