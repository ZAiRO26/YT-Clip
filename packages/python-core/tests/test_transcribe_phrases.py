from clipforge_core.workers.transcribe import _split_into_phrases


def _words(*spans):
    return [{"word": w, "start": s, "end": e} for w, s, e in spans]


def test_splits_at_pause_and_sentence_end():
    words = _words(
        ("so", 0.0, 0.2), ("anyway.", 0.2, 0.6),   # sentence end
        ("next", 0.7, 0.9), ("thing", 0.9, 1.2),   # pause follows
        ("after", 2.0, 2.3), ("pause", 2.3, 2.6),
    )
    phrases = _split_into_phrases(words)
    assert [[w["word"] for w in p] for p in phrases] == [["so", "anyway."], ["next", "thing"], ["after", "pause"]]


def test_caps_phrase_length_for_unbroken_speech():
    words = _words(*[(f"w{i}", i * 0.5, i * 0.5 + 0.5) for i in range(60)])  # 30s, no pauses
    phrases = _split_into_phrases(words)
    assert all(p[-1]["end"] - p[0]["start"] <= 5.0 for p in phrases)
    assert sum(len(p) for p in phrases) == 60  # no word lost or duplicated
