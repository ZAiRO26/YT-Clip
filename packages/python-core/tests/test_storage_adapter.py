from clipforge_core.services.storage import LocalStorageAdapter, S3StorageAdapter


def test_local_storage_adapter_save_and_get(tmp_path):
    storage = LocalStorageAdapter(base_dir=tmp_path)

    # Create dummy source
    src_file = tmp_path / "source.txt"
    src_file.write_text("Local storage test payload", encoding="utf-8")

    key = "projects/p1/clips/clip.txt"
    url = storage.save_file(src_file, key)
    assert url == "media/projects/p1/clips/clip.txt"
    assert storage.file_exists(key)

    dest_file = tmp_path / "downloaded.txt"
    storage.get_file(key, dest_file)
    assert dest_file.exists()
    assert dest_file.read_text(encoding="utf-8") == "Local storage test payload"

    assert storage.delete_file(key) is True
    assert not storage.file_exists(key)


def test_s3_storage_fallback():
    s3 = S3StorageAdapter(bucket_name="clipforge")
    assert s3.local_fallback is not None
