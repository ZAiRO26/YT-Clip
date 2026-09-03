"""
Tests for ClipForge AI Native File & Folder Dialog Utility.
"""
from unittest.mock import patch
from clipforge_core.services.file_picker import pick_file_sync, pick_folder_sync


def test_pick_file_sync_mock_selection():
    with patch("tkinter.filedialog.askopenfilename", return_value="D:/Videos/my_video.mp4"):
        with patch("tkinter.Tk"):
            res = pick_file_sync()
            assert res["cancelled"] is False
            assert "my_video.mp4" in res["file_path"]


def test_pick_file_sync_mock_cancellation():
    with patch("tkinter.filedialog.askopenfilename", return_value=""):
        with patch("tkinter.Tk"):
            res = pick_file_sync()
            assert res["cancelled"] is True
            assert res["file_path"] == ""


def test_pick_folder_sync_mock_selection():
    with patch("tkinter.filedialog.askdirectory", return_value="D:/ExportFolder"):
        with patch("tkinter.Tk"):
            res = pick_folder_sync()
            assert res["cancelled"] is False
            assert "ExportFolder" in res["folder_path"]


def test_pick_folder_sync_mock_cancellation():
    with patch("tkinter.filedialog.askdirectory", return_value=""):
        with patch("tkinter.Tk"):
            res = pick_folder_sync()
            assert res["cancelled"] is True
            assert res["folder_path"] == ""
