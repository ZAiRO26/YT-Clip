"""
ClipForge AI — Native File & Folder Dialog Utility
Allows users to open Windows Explorer file dialog to pick local video files and folders.
Uses an external STA PowerShell process on Windows to ensure modal dialog appears on top
and does not hang or conflict with server-side async worker threads.
"""
import logging
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).resolve().parents[4] / "scripts"


def pick_file_sync(title: str = "Select Video File", initial_dir: Optional[str] = None) -> Dict[str, Any]:
    """Open native OS file picker dialog."""
    if platform.system() == "Windows":
        script_path = SCRIPTS_DIR / "open_file_dialog.ps1"
        if script_path.exists():
            try:
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Sta",
                    "-File",
                    str(script_path),
                    "-Title",
                    title,
                ]
                if initial_dir and Path(initial_dir).exists():
                    cmd.extend(["-InitialDirectory", initial_dir])

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                output = result.stdout.strip()
                for line in output.splitlines():
                    if line.startswith("SELECTED:"):
                        raw_path = line[len("SELECTED:") :].strip()
                        resolved = str(Path(raw_path).resolve())
                        return {"file_path": resolved, "cancelled": False}
                    elif line.startswith("CANCELLED"):
                        return {"file_path": "", "cancelled": True}

                return {"file_path": "", "cancelled": True}
            except subprocess.TimeoutExpired:
                logger.warning("Native file picker timed out after 120s")
                return {"file_path": "", "cancelled": True, "error": "Dialog timed out"}
            except Exception as e:
                logger.error(f"PowerShell file picker error: {e}")

    # Fallback to Tkinter for cross-platform / fallback
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = filedialog.askopenfilename(
            parent=root,
            title=title,
            initialdir=initial_dir or None,
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.mov *.webm *.avi *.flv *.ts *.m4v"),
                ("All Files", "*.*"),
            ],
        )
        root.destroy()

        if file_path:
            norm_path = str(Path(file_path).resolve())
            return {"file_path": norm_path, "cancelled": False}
        return {"file_path": "", "cancelled": True}
    except Exception as e:
        logger.error(f"Fallback Tkinter file picker error: {e}")
        return {"file_path": "", "cancelled": True, "error": str(e)}


def pick_folder_sync(title: str = "Select Destination Folder", initial_dir: Optional[str] = None) -> Dict[str, Any]:
    """Open native OS directory picker dialog."""
    if platform.system() == "Windows":
        script_path = SCRIPTS_DIR / "open_folder_dialog.ps1"
        if script_path.exists():
            try:
                cmd = [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Sta",
                    "-File",
                    str(script_path),
                    "-Description",
                    title,
                ]
                if initial_dir and Path(initial_dir).exists():
                    cmd.extend(["-SelectedPath", initial_dir])

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                output = result.stdout.strip()
                for line in output.splitlines():
                    if line.startswith("SELECTED:"):
                        raw_path = line[len("SELECTED:") :].strip()
                        resolved = str(Path(raw_path).resolve())
                        return {"folder_path": resolved, "cancelled": False}
                    elif line.startswith("CANCELLED"):
                        return {"folder_path": "", "cancelled": True}

                return {"folder_path": "", "cancelled": True}
            except subprocess.TimeoutExpired:
                logger.warning("Native folder picker timed out after 120s")
                return {"folder_path": "", "cancelled": True, "error": "Dialog timed out"}
            except Exception as e:
                logger.error(f"PowerShell folder picker error: {e}")

    # Fallback to Tkinter
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        folder_path = filedialog.askdirectory(
            parent=root,
            title=title,
            initialdir=initial_dir or None,
        )
        root.destroy()

        if folder_path:
            norm_path = str(Path(folder_path).resolve())
            return {"folder_path": norm_path, "cancelled": False}
        return {"folder_path": "", "cancelled": True}
    except Exception as e:
        logger.error(f"Fallback Tkinter folder picker error: {e}")
        return {"folder_path": "", "cancelled": True, "error": str(e)}
