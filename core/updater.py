"""
yt-dlp update functionality for Media Downloader App
"""

import sys
import subprocess
import json
import urllib.request
from PyQt5.QtCore import QThread, pyqtSignal


def get_ytdlp_version():
    """Get the currently installed yt-dlp version."""
    try:
        import yt_dlp.version
        return yt_dlp.version.__version__
    except Exception:
        return "unknown"


def is_frozen():
    """Check if running as a frozen/packaged PyInstaller app."""
    return getattr(sys, 'frozen', False)


class VersionCheckWorker(QThread):
    """Background thread that checks GitHub for the latest yt-dlp version."""
    # latest_version (str or None if check failed)
    finished = pyqtSignal(str)

    def run(self):
        try:
            url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "MediaDownloader/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            latest = data.get("tag_name", "").lstrip("v")
            print(f"[DEBUG] yt-dlp latest version from GitHub: {latest}")
            self.finished.emit(latest or "")
        except Exception as e:
            print(f"[DEBUG] yt-dlp version check failed: {e}")
            self.finished.emit("")


class InstallUpdateWorker(QThread):
    """Background thread that installs a yt-dlp update via pip."""
    status_update = pyqtSignal(str)
    # success, message, new_version
    finished = pyqtSignal(bool, str, str)

    def __init__(self, target_version):
        super().__init__()
        self.target_version = target_version

    def run(self):
        current = get_ytdlp_version()
        try:
            if is_frozen():
                self.finished.emit(
                    False,
                    f"Re-download the app to update to {self.target_version}",
                    current
                )
                return

            self.status_update.emit("Updating...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                capture_output=True, text=True, timeout=120
            )

            if result.returncode != 0:
                print(f"[DEBUG] pip upgrade stderr: {result.stderr}")
                self.finished.emit(False, f"Update failed: {result.stderr[:120]}", current)
                return

            # Re-read version after upgrade (module cache may be stale)
            ver_result = subprocess.run(
                [sys.executable, "-c",
                 "import yt_dlp.version; print(yt_dlp.version.__version__)"],
                capture_output=True, text=True, timeout=10
            )
            new_version = ver_result.stdout.strip() if ver_result.returncode == 0 else self.target_version

            print(f"[DEBUG] yt-dlp updated to: {new_version}")
            self.finished.emit(True, f"Updated from {current}", new_version)

        except Exception as e:
            print(f"[DEBUG] Update error: {e}")
            self.finished.emit(False, f"Update failed: {e}", current)
