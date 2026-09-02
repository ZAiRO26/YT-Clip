"""
ClipForge AI — Royalty-Free Background Music Studio (v2)
Provides ambient background music beds with auto-ducking mixing profiles.
"""
import subprocess
from pathlib import Path
from typing import Any, Dict, List

MUSIC_TRACKS: List[Dict[str, Any]] = [
    {
        "id": "none",
        "name": "No Background Music",
        "genre": "None",
        "bpm": 0,
        "energy": "None",
    },
    {
        "id": "ambient_focus",
        "name": "Ambient Focus",
        "genre": "Ambient / Minimal",
        "bpm": 80,
        "energy": "Low (Best for Educational / Explainers)",
        "default_volume_db": -22.0,
    },
    {
        "id": "lofi_beats",
        "name": "Chill Lo-Fi",
        "genre": "Lo-Fi Hip Hop",
        "bpm": 85,
        "energy": "Medium-Low (Best for Commentary / Podcasts)",
        "default_volume_db": -20.0,
    },
    {
        "id": "upbeat_tech",
        "name": "Upbeat Modern Tech",
        "genre": "Electronic / Tech",
        "bpm": 115,
        "energy": "High (Best for Fast News / Announcements)",
        "default_volume_db": -22.0,
    },
    {
        "id": "epic_cinematic",
        "name": "Cinematic Tension",
        "genre": "Cinematic Orchestral",
        "bpm": 90,
        "energy": "Dramatic (Best for Story Loops / Debates)",
        "default_volume_db": -24.0,
    },
]


def ensure_synth_bed(track_id: str, output_path: str | Path, duration_sec: float = 60.0) -> Path:
    """
    Generates a synthetic ambient audio bed if pre-bundled MP3 is not present.
    Uses multi-oscillator chord progressions, rhythmic pulses, and subtle textures.
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if track_id == "none":
        return out_path

    # Rich harmonic multi-oscillator synthesizer definitions per mood with loudnorm mastering
    if track_id == "lofi_beats":
        # Warm Dmin7 jazzy chord + rhythmic pulse + tape texture
        filter_str = (
            "sine=f=146.83:r=44100[s1];sine=f=174.61:r=44100[s2];sine=f=220.0:r=44100[s3];sine=f=261.63:r=44100[s4];"
            "anoisesrc=c=pink:r=44100:a=0.015[nz];"
            "[s1][s2][s3][s4][nz]amix=inputs=5:normalize=0,volume=1.2,tremolo=f=1.5:d=0.55,flanger=delay=4:depth=2,lowpass=f=1800,"
            "loudnorm=I=-16:TP=-1.5:LRA=7[aout]"
        )
    elif track_id == "upbeat_tech":
        # Modern electronic tech pulse with 4-on-the-floor 3.5Hz rhythmic gate
        filter_str = (
            "sine=f=130.81:r=44100[s1];sine=f=196.0:r=44100[s2];sine=f=261.63:r=44100[s3];sine=f=329.63:r=44100[s4];sine=f=523.25:r=44100[s5];"
            "[s1][s2][s3][s4][s5]amix=inputs=5:normalize=0,volume=1.3,tremolo=f=3.5:d=0.8,chorus=0.7:0.9:45:0.4:0.3:2,"
            "loudnorm=I=-16:TP=-1.5:LRA=7[aout]"
        )
    elif track_id == "epic_cinematic":
        # Deep cinematic brass + strings 5th power chord with low drone
        filter_str = (
            "sine=f=82.41:r=44100[s1];sine=f=123.47:r=44100[s2];sine=f=164.81:r=44100[s3];sine=f=246.94:r=44100[s4];sine=f=329.63:r=44100[s5];"
            "[s1][s2][s3][s4][s5]amix=inputs=5:normalize=0,volume=1.2,tremolo=f=0.4:d=0.45,lowpass=f=1200,"
            "loudnorm=I=-16:TP=-1.5:LRA=7[aout]"
        )
    else:  # ambient_focus
        # Lush ambient pad with chorus and subtle tremolo (Cmaj7 / Am9)
        filter_str = (
            "sine=f=220.0:r=44100[s1];sine=f=277.18:r=44100[s2];sine=f=329.63:r=44100[s3];sine=f=440.0:r=44100[s4];sine=f=523.25:r=44100[s5];"
            "[s1][s2][s3][s4][s5]amix=inputs=5:normalize=0,volume=1.2,tremolo=f=0.6:d=0.35,chorus=0.7:0.9:55:0.4:0.25:2,lowpass=f=1600,"
            "loudnorm=I=-16:TP=-1.5:LRA=7[aout]"
        )

    cmd = [
        "ffmpeg",
        "-y",
        "-filter_complex", filter_str,
        "-map", "[aout]",
        "-t", str(duration_sec),
        "-c:a", "aac",
        "-b:a", "192k",
        str(out_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    return out_path
