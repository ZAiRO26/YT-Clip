import json
import subprocess
from pathlib import Path

from clipforge_core.services.audio_mixer import mix_audio_tracks
from clipforge_core.services.tts_service import synthesize_voiceover

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _measure_lufs(audio_path: Path) -> float:
    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-af", "loudnorm=I=-14:LRA=7:TP=-1.5:print_format=json",
        "-f", "null",
        "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    stderr = proc.stderr
    start_json = stderr.find("{")
    end_json = stderr.rfind("}") + 1
    if start_json != -1 and end_json > start_json:
        data = json.loads(stderr[start_json:end_json])
        return float(data.get("input_i", -99.0))
    raise RuntimeError("Failed to parse loudnorm JSON from FFmpeg stderr")


def test_mix_audio_tracks_with_sidechain_ducking(tmp_path):
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    vo_audio = tmp_path / "vo.wav"
    synthesize_voiceover(
        "Welcome to the lecture. Notice the progression of ideas throughout the modern period.",
        voice_id="af_bella",
        output_path=vo_audio,
    )

    out_mixed = tmp_path / "mastered_audio.aac"
    res = mix_audio_tracks(
        source_video_path=fixture,
        output_audio_path=out_mixed,
        start_sec=1.0,
        end_sec=6.0,
        voiceover_path=vo_audio,
        voiceover_delay_sec=0.5,
    )

    assert out_mixed.exists(), "Mastered audio not generated"
    assert out_mixed.stat().st_size > 1000
    assert res["has_voiceover"] is True
    assert res["has_music"] is False

    # Check objective loudness measurement (-14.0 +/- 1.0 LUFS)
    measured_i = _measure_lufs(out_mixed)
    assert -15.0 <= measured_i <= -13.0, f"Expected LUFS within [-15.0, -13.0], got {measured_i}"


def test_mix_audio_tracks_source_only(tmp_path):
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    out_norm = tmp_path / "norm_source.aac"
    res = mix_audio_tracks(
        source_video_path=fixture,
        output_audio_path=out_norm,
        start_sec=1.0,
        end_sec=6.0,
        voiceover_path=None,
    )

    assert out_norm.exists()
    assert res["has_voiceover"] is False
    assert res["has_music"] is False

    measured_i = _measure_lufs(out_norm)
    assert -15.0 <= measured_i <= -13.0, f"Expected LUFS within [-15.0, -13.0], got {measured_i}"
