"""
Unit tests for silence gap detection and voiceover start offset computation.
"""
import pytest
from clipforge_core.services.gap_detector import compute_voiceover_start_offset, find_silence_gaps


def test_find_silence_gaps_detects_middle_gap():
    """Detects a 4.0s pause between two dialogue segments."""
    segments = [
        {"start": 10.0, "end": 15.0, "text": "Hello world"},
        {"start": 19.0, "end": 25.0, "text": "Welcome back"},
    ]
    # Clip from 10.0 to 25.0
    gaps = find_silence_gaps(segments, clip_start_sec=10.0, clip_end_sec=25.0, min_gap_sec=3.0)
    assert len(gaps) == 1
    assert gaps[0]["start_offset_sec"] == 5.0  # 15.0 - 10.0
    assert gaps[0]["end_offset_sec"] == 9.0    # 19.0 - 10.0
    assert gaps[0]["duration_sec"] == 4.0


def test_find_silence_gaps_detects_leading_and_trailing():
    """Detects gaps at start and end of clip."""
    segments = [
        {"start": 14.0, "end": 18.0, "text": "Mid clip speech"},
    ]
    # Clip from 10.0 to 22.0 (4.0s leading gap, 4.0s trailing gap)
    gaps = find_silence_gaps(segments, clip_start_sec=10.0, clip_end_sec=22.0, min_gap_sec=3.0)
    assert len(gaps) == 2
    assert gaps[0]["start_offset_sec"] == 0.0
    assert gaps[0]["duration_sec"] == 4.0
    assert gaps[1]["start_offset_sec"] == 8.0  # 18.0 - 10.0
    assert gaps[1]["duration_sec"] == 4.0


def test_find_silence_gaps_ignores_short_pauses():
    """Pauses shorter than min_gap_sec (e.g. 1.2s) must NOT qualify."""
    segments = [
        {"start": 5.0, "end": 8.0, "text": "First sentence"},
        {"start": 9.2, "end": 12.0, "text": "Second sentence"},  # 1.2s pause
    ]
    gaps = find_silence_gaps(segments, clip_start_sec=5.0, clip_end_sec=12.0, min_gap_sec=3.0)
    assert len(gaps) == 0


def test_compute_voiceover_start_offset_hook_intro():
    """Hook intro starts at 0.5s."""
    offset = compute_voiceover_start_offset(
        style="hook_intro",
        clip_duration_sec=30.0,
        script_word_count=8,
        gaps=[],
    )
    assert offset == 0.5


def test_compute_voiceover_start_offset_outro_cta():
    """Outro CTA is anchored to finish 0.5s before clip end."""
    # 10 words @ 2.8 wps = ~3.57s duration
    # 30.0 - 3.57 - 0.5 = 25.93s
    offset = compute_voiceover_start_offset(
        style="outro_cta",
        clip_duration_sec=30.0,
        script_word_count=10,
        gaps=[],
        speaking_rate_wps=2.8,
    )
    assert 25.0 <= offset <= 26.5
    assert offset + (10 / 2.8) <= 30.0  # Finished before clip end


def test_compute_voiceover_start_offset_explainer_gap_anchored():
    """Explainer anchors to the first qualifying gap."""
    gaps = [{"start_offset_sec": 7.5, "end_offset_sec": 12.0, "duration_sec": 4.5}]
    offset = compute_voiceover_start_offset(
        style="explainer",
        clip_duration_sec=30.0,
        script_word_count=18,
        gaps=gaps,
    )
    assert offset == 7.7  # 7.5 + 0.2s padding


def test_compute_voiceover_start_offset_outro_cta_two_pass_exact():
    """Two-pass Outro CTA with actual measured audio duration guarantees exact 0.5s buffer."""
    clip_dur = 24.50
    actual_audio_dur = 2.97
    buffer_sec = 0.50

    offset = compute_voiceover_start_offset(
        style="outro_cta",
        clip_duration_sec=clip_dur,
        script_word_count=8,
        gaps=[],
        actual_audio_duration_sec=actual_audio_dur,
        buffer_sec=buffer_sec,
    )
    # Expected: 24.50 - 2.97 - 0.50 = 21.03s
    assert offset == 21.03
    # Margin before clip cut must be EXACTLY buffer_sec (0.50s)
    assert round(clip_dur - (offset + actual_audio_dur), 2) == 0.50

