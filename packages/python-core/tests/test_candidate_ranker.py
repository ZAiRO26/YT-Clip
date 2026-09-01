from clipforge_core.services.candidate_ranker import (
    deduplicate_and_rank_candidates,
    snap_to_scene_boundaries,
)


def test_snap_to_scene_boundaries():
    scenes = [
        {"scene_id": 1, "start_sec": 0.0, "end_sec": 14.8},
        {"scene_id": 2, "start_sec": 14.8, "end_sec": 32.1},
        {"scene_id": 3, "start_sec": 32.1, "end_sec": 60.0},
    ]

    # Start 15.0 is close to scene 2 start (14.8) -> should snap to 14.8
    # End 31.9 is close to scene 2 end (32.1) -> should snap to 32.1
    s, e = snap_to_scene_boundaries(15.0, 31.9, scenes, tolerance_sec=1.0)
    assert s == 14.8
    assert e == 32.1


def test_deduplicate_and_rank_candidates():
    candidates = [
        {
            "start_sec": 10.0,
            "end_sec": 40.0,
            "virality_score": 0.9,
            "transformation_score": 80,
            "title": "Top Clip",
        },
        {
            "start_sec": 12.0,
            "end_sec": 38.0,  # Overlaps significantly with Top Clip
            "virality_score": 0.5,
            "transformation_score": 40,
            "title": "Duplicate Clip",
        },
        {
            "start_sec": 50.0,
            "end_sec": 80.0,
            "virality_score": 0.8,
            "transformation_score": 75,
            "title": "Second Distinct Clip",
        },
    ]

    ranked = deduplicate_and_rank_candidates(candidates)
    assert len(ranked) == 2
    assert ranked[0]["title"] == "Top Clip"
    assert ranked[1]["title"] == "Second Distinct Clip"
