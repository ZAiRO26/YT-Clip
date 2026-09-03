"""
Tests for ClipForge AI Native File & Folder Dialog Utility.
"""
from unittest.mock import MagicMock, patch
from clipforge_core.services.file_picker import pick_file_sync, pick_folder_sync


def test_pick_file_sync_mock_selection():
    mock_proc = MagicMock()
    mock_proc.stdout = "SELECTED: D:/Videos/my_video.mp4\n"
    with patch("subprocess.run", return_value=mock_proc):
        res = pick_file_sync()
        assert res["cancelled"] is False
        assert "my_video.mp4" in res["file_path"]


def test_pick_file_sync_mock_cancellation():
    mock_proc = MagicMock()
    mock_proc.stdout = "CANCELLED\n"
    with patch("subprocess.run", return_value=mock_proc):
        res = pick_file_sync()
        assert res["cancelled"] is True
        assert res["file_path"] == ""


def test_pick_folder_sync_mock_selection():
    mock_proc = MagicMock()
    mock_proc.stdout = "SELECTED: D:/ExportFolder\n"
    with patch("subprocess.run", return_value=mock_proc):
        res = pick_folder_sync()
        assert res["cancelled"] is False
        assert "ExportFolder" in res["folder_path"]


def test_pick_folder_sync_mock_cancellation():
    mock_proc = MagicMock()
    mock_proc.stdout = "CANCELLED\n"
    with patch("subprocess.run", return_value=mock_proc):
        res = pick_folder_sync()
        assert res["cancelled"] is True
        assert res["folder_path"] == ""
