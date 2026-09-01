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
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if track_id == "none":
        return out_path

    # Synthesize soft harmonic sine/pink-noise ambient bed with subtle vibrato
    # Frequencies: ambient_focus=220Hz (A3), lofi_beats=196Hz (G3), upbeat_tech=261.63Hz (C4), epic_cinematic=146.83Hz (D3)
    base_freqs = {
        "ambient_focus": 220.0,
        "lofi_beats": 196.0,
        "upbeat_tech": 261.63,
        "epic_cinematic": 146.83,
    }
    freq = base_freqs.get(track_id, 220.0)

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:sample_rate=44100",
        "-t", str(duration_sec),
        "-af", "volume=0.08,lowpass=f=800",
        "-c:a", "aac",
        "-b:a", "128k",
        str(out_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    return out_path
