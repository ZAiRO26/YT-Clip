from clipforge_core.services.cleanup import cleanup_project_temp_files


def test_cleanup_project_temp_files_preserves_finals(tmp_path, monkeypatch):
    # Set up simulated media directory structure
    project_id = "test-project-123"
    proj_dir = tmp_path / project_id
    proj_dir.mkdir(parents=True)
    clips_dir = proj_dir / "clips"
    clips_dir.mkdir()

    # Create dummy files
    final_video = clips_dir / "clip_1.mp4"
    final_video.write_bytes(b"final video bytes")

    final_thumb = clips_dir / "clip_1_thumb.jpg"
    final_thumb.write_bytes(b"thumbnail bytes")

    temp_draft = clips_dir / "temp_cut.tmp"
    temp_draft.write_bytes(b"temp cut bytes")

    temp_vo = clips_dir / "vo_123.mp3"
    temp_vo.write_bytes(b"temporary vo bytes")

    monkeypatch.setattr("clipforge_core.services.cleanup.settings.MEDIA_DIR", str(tmp_path))

    res = cleanup_project_temp_files(project_id=project_id, max_age_hours=0.0)

    assert res["deleted_count"] == 2
    assert not temp_draft.exists(), "Temporary cut should be purged"
    assert not temp_vo.exists(), "Temporary VO should be purged"
    assert final_video.exists(), "Final video must be preserved"
    assert final_thumb.exists(), "Final thumbnail must be preserved"
