"""
Window utility functions for Media Downloader App
Cross-platform window activation and bring-to-front functionality
"""

import sys


def activate_app():
    """
    Activate the application and bring it to the foreground.

    On macOS, uses NSApplication to properly activate the app.
    On other platforms, this is a no-op (Qt methods handle it).
    """
    if sys.platform == "darwin":
        try:
            from AppKit import NSApplication, NSApp
            NSApp.activateIgnoringOtherApps_(True)
        except ImportError:
            # PyObjC not installed, fall back to Qt-only methods
            pass


def bring_window_to_front(window):
    """
    Bring a Qt window to the front and activate it.

    Args:
        window: QWidget or QMainWindow instance to bring to front
    """
    if window is None:
        return

    # First, activate the app on macOS
    activate_app()

    # Show window if hidden
    if not window.isVisible():
        window.show()

    # Restore if minimized
    if window.isMinimized():
        window.showNormal()

    # Bring to front and activate
    window.raise_()
    window.activateWindow()


def bring_dialog_to_front(dialog, parent_window=None):
    """
    Bring a dialog to the front, optionally with its parent window.

    Args:
        dialog: QDialog instance to bring to front
        parent_window: Optional parent window to also bring to front
    """
    # First activate the app on macOS
    activate_app()

    # Bring parent window to front first if provided
    if parent_window is not None:
        bring_window_to_front(parent_window)

    # Now bring the dialog to front
    if dialog is not None:
        dialog.raise_()
        dialog.activateWindow()
