"""
macOS integrations: Dock visibility + Login Items.

Wraps AppKit (pyobjc) and osascript so the rest of the app doesn't import
platform-specific modules directly. Every function silently no-ops on
non-darwin systems and on unexpected failures — these are UX preferences,
never load-bearing for downloading.
"""

import platform
import subprocess
import sys
from pathlib import Path


IS_MACOS = platform.system() == "Darwin"
LOGIN_ITEM_NAME = "dlwithit"


def set_dock_visible(visible):
    """Show or hide the Dock icon at runtime via NSApp activation policy.

    Regular = Dock icon + standard app behavior.
    Accessory = no Dock icon, app stays alive in the menu bar.
    """
    if not IS_MACOS:
        return
    try:
        from AppKit import (
            NSApp,
            NSApplicationActivationPolicyAccessory,
            NSApplicationActivationPolicyRegular,
        )

        policy = (
            NSApplicationActivationPolicyRegular
            if visible
            else NSApplicationActivationPolicyAccessory
        )
        NSApp.setActivationPolicy_(policy)
    except Exception:
        pass


def refresh_dock_icon(icon_path):
    """Re-apply the Dock icon image.

    macOS forgets the previously-set Dock icon when activation policy
    goes Accessory→Regular, falling back to the bare executable icon
    (the Python rocket in dev). Call this after set_dock_visible(True)
    to put our icon back.
    """
    if not IS_MACOS:
        return
    try:
        from AppKit import NSApp, NSImage

        img = NSImage.alloc().initByReferencingFile_(icon_path)
        if img:
            NSApp.setApplicationIconImage_(img)
    except Exception:
        pass


def _bundle_path():
    """Best-effort path to the dlwithit.app bundle for login-item registration.

    When running as a frozen PyInstaller .app, walk up from sys.executable
    to find the .app root. In dev (running native_app.py), fall back to the
    expected install location — the login item will register but won't
    point at the dev process, which is the right behavior.
    """
    if getattr(sys, "frozen", False):
        for parent in Path(sys.executable).parents:
            if parent.suffix == ".app":
                return str(parent)
    return "/Applications/dlwithit.app"


def set_launch_at_login(enabled, hidden=True):
    """Register or remove dlwithit as a macOS login item.

    The `hidden` flag asks macOS to launch the app without bringing its
    window forward; pair with the --hidden CLI flag in native_app.py to
    suppress the window on startup.
    """
    if not IS_MACOS:
        return
    bundle = _bundle_path()
    hidden_str = "true" if hidden else "false"
    try:
        if enabled:
            script = (
                f'tell application "System Events" to make login item '
                f'at end with properties {{name:"{LOGIN_ITEM_NAME}", '
                f'path:"{bundle}", hidden:{hidden_str}}}'
            )
        else:
            script = (
                f'tell application "System Events" to delete login item '
                f'"{LOGIN_ITEM_NAME}"'
            )
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            timeout=10,
            capture_output=True,
        )
    except Exception:
        pass


def is_launch_at_login_enabled():
    """True if dlwithit is currently registered as a macOS login item."""
    if not IS_MACOS:
        return False
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get the name of every login item',
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return LOGIN_ITEM_NAME in (result.stdout or "")
    except Exception:
        return False
