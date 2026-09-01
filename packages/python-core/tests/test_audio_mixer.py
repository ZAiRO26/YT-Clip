from pathlib import Path
from clipforge_core.services.audio_mixer import mix_audio_tracks
from clipforge_core.services.music_library import ensure_synth_bed
from clipforge_core.services.tts_service import synthesize_voiceover

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_mix_audio_tracks_with_sidechain_ducking(tmp_path):
    fixture = FIXTURES_DIR / "authorized_explainer_1080p.mp4"
    assert fixture.exists(), "Fixture missing"

    vo_audio = tmp_path / "vo.mp3"
    synthesize_voiceover("This is original editorial analysis for this clip.", output_path=vo_audio)

    bg_music = tmp_path / "ambient.aac"
    ensure_synth_bed("ambient_focus", bg_music, duration_sec=10.0)

    out_mixed = tmp_path / "mastered_audio.aac"
    res = mix_audio_tracks(
        source_video_path=fixture,
        output_audio_path=out_mixed,
        start_sec=1.0,
        end_sec=5.0,
        voiceover_path=vo_audio,
        music_path=bg_music,
        voiceover_delay_sec=0.2,
    )

    assert out_mixed.exists(), "Mastered audio not generated"
    assert out_mixed.stat().st_size > 1000
    assert res["has_voiceover"] is True
    assert res["has_music"] is True
