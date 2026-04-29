"""
dlwithit self-update check (GitHub Releases API).

v1 flow: check the latest release on launch. If newer than the running version,
surface a clickable "Update available" link in Settings and fire a one-shot
macOS notification. The user downloads the new .pkg from GitHub manually.

When the repo has no published releases yet, the API returns 404 and the
check silently no-ops — no error UI, no notification.
"""

import json
import platform
import subprocess
import urllib.error
import urllib.request

from PyQt5.QtCore import QThread, pyqtSignal


GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/techweather/video-downloader-extension/releases/latest"
)


def parse_version(s):
    """Parse 'X.Y.Z' (optionally 'vX.Y.Z') into a tuple of ints, or None."""
    if not s:
        return None
    parts = s.strip().lstrip("v").split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def is_newer(latest, current):
    """True when `latest` is a strictly newer version than `current`."""
    lv = parse_version(latest)
    cv = parse_version(current)
    if lv is None or cv is None:
        return False
    return lv > cv


def notify_update_available(latest):
    """Fire a macOS notification announcing an available update.

    No-op on non-darwin or if osascript fails — the Settings link remains the
    primary affordance.
    """
    if platform.system() != "Darwin":
        return
    title = "dlwithit update available"
    msg = f"Version {latest} is out — open Settings to view the release."
    safe_title = title.replace('"', "")
    safe_msg = msg.replace('"', "")
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{safe_msg}" with title "{safe_title}"',
            ],
            check=False,
            timeout=5,
        )
    except Exception:
        pass


class AppVersionCheckWorker(QThread):
    """Background thread that asks GitHub for the latest dlwithit release.

    Emits (latest_version, release_url). Both empty strings when no releases
    are published yet (HTTP 404), the network call fails, or the response is
    missing required fields.
    """

    finished = pyqtSignal(str, str)

    def run(self):
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_URL,
                headers={"User-Agent": "dlwithit/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            latest = (data.get("tag_name") or "").lstrip("v")
            url = data.get("html_url") or ""
            self.finished.emit(latest, url)
        except urllib.error.HTTPError:
            # 404 (no releases yet) and other HTTP errors: silent no-op.
            self.finished.emit("", "")
        except Exception:
            self.finished.emit("", "")
