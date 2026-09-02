"""
ClipForge AI — Audio Studio & Sidechain Ducking Mixer (v2)
Mixes source video audio, original voiceover narration, and ambient background music
with sidechain compression ducking and loudnorm mastering (-14.0 LUFS).
"""
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
) -> Dict[str, Any]:
    """
    Mixes audio streams into a mastered AAC track with sidechain ducking.
    """
    src_vid = Path(source_video_path)
    out_audio = Path(output_audio_path)
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    duration = end_sec - start_sec

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
        # Delay VO if requested and pad with silence so ducking releases cleanly after narration finishes
        delay_ms = int(voiceover_delay_sec * 1000)
        filter_complex_parts.append(f"[{vo_idx}:a]adelay={delay_ms}|{delay_ms},volume=1.0,apad[vo_delayed];")
        # Duck source and music under VO
        filter_complex_parts.append(f"[{music_idx}:a]volume={music_volume_db}dB[bg_low];")
        filter_complex_parts.append(
            "[0:a][vo_delayed]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[ducked_src];"
            "[bg_low][vo_delayed]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=300[ducked_bg];"
            "[ducked_src][vo_delayed][ducked_bg]amix=inputs=3:duration=first:dropout_transition=2,"
            "loudnorm=I=-14:LRA=7:TP=-1.5[aout]"
        )
    elif vo_idx is not None:
        # 2 streams: Source and VO
        delay_ms = int(voiceover_delay_sec * 1000)
        filter_complex_parts.append(f"[{vo_idx}:a]adelay={delay_ms}|{delay_ms},volume=1.0,apad[vo_delayed];")
        filter_complex_parts.append(
            "[0:a][vo_delayed]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[ducked_src];"
            "[ducked_src][vo_delayed]amix=inputs=2:duration=first:dropout_transition=2,"
            "loudnorm=I=-14:LRA=7:TP=-1.5[aout]"
        )
    elif music_idx is not None:
        # 2 streams: Source and Music
        filter_complex_parts.append(
            f"[{music_idx}:a]volume={music_volume_db}dB[bg_low];"
            f"[0:a][bg_low]amix=inputs=2:duration=first:dropout_transition=2,"
            f"loudnorm=I=-14:LRA=7:TP=-1.5[aout]"
        )
    else:
        # 1 stream: Just source normalized
        filter_complex_parts.append("[0:a]loudnorm=I=-14:LRA=7:TP=-1.5[aout]")

    filter_str = "".join(filter_complex_parts)

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[aout]",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-t", str(duration),
        str(out_audio),
    ]

    logger.info(f"[AudioMixer] Mixing audio tracks (VO={'yes' if vo_idx else 'no'}, Music={'yes' if music_idx else 'no'})")
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60, check=True)

    return {
        "output_path": str(out_audio),
        "has_voiceover": vo_idx is not None,
        "has_music": music_idx is not None,
        "duration_sec": duration,
    }
