"""
Tests for core.macos — Dock visibility + login-item helpers.

These mock AppKit and subprocess so the tests don't actually toggle the
Dock icon or write a real login item. We're verifying the right calls
get made with the right arguments, and that failures are swallowed
silently (UX preferences should never crash the app).
"""

import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.macos as macos


@pytest.fixture
def force_macos():
    """Pretend we're on darwin for tests that need it."""
    with mock.patch.object(macos, "IS_MACOS", True):
        yield


@pytest.fixture
def force_non_macos():
    with mock.patch.object(macos, "IS_MACOS", False):
        yield


class TestSetDockVisible:
    def test_calls_appkit_with_regular_when_visible(self, force_macos):
        fake_app = mock.MagicMock()
        fake_appkit = mock.MagicMock()
        fake_appkit.NSApp = fake_app
        fake_appkit.NSApplicationActivationPolicyRegular = 0
        fake_appkit.NSApplicationActivationPolicyAccessory = 1
        with mock.patch.dict(sys.modules, {"AppKit": fake_appkit}):
            macos.set_dock_visible(True)
        fake_app.setActivationPolicy_.assert_called_once_with(0)

    def test_calls_appkit_with_accessory_when_hidden(self, force_macos):
        fake_app = mock.MagicMock()
        fake_appkit = mock.MagicMock()
        fake_appkit.NSApp = fake_app
        fake_appkit.NSApplicationActivationPolicyRegular = 0
        fake_appkit.NSApplicationActivationPolicyAccessory = 1
        with mock.patch.dict(sys.modules, {"AppKit": fake_appkit}):
            macos.set_dock_visible(False)
        fake_app.setActivationPolicy_.assert_called_once_with(1)

    def test_no_op_on_non_macos(self, force_non_macos):
        # Should not even attempt to import AppKit on non-darwin.
        # If it tried, mocking would be needed; the no-op path returns first.
        macos.set_dock_visible(True)  # must not raise
        macos.set_dock_visible(False)

    def test_swallows_appkit_failure(self, force_macos):
        # AppKit import or call failure must never propagate — UX prefs
        # are not load-bearing for downloads.
        with mock.patch.dict(sys.modules, {"AppKit": None}):
            macos.set_dock_visible(True)  # AppKit=None triggers AttributeError on access


class TestRefreshDockIcon:
    def test_calls_setapplicationiconimage_with_loaded_image(self, force_macos):
        fake_app = mock.MagicMock()
        fake_image_class = mock.MagicMock()
        fake_image = mock.MagicMock()
        fake_image_class.alloc.return_value.initByReferencingFile_.return_value = fake_image
        fake_appkit = mock.MagicMock()
        fake_appkit.NSApp = fake_app
        fake_appkit.NSImage = fake_image_class
        with mock.patch.dict(sys.modules, {"AppKit": fake_appkit}):
            macos.refresh_dock_icon("/path/to/icon.png")
        fake_image_class.alloc.return_value.initByReferencingFile_.assert_called_once_with(
            "/path/to/icon.png"
        )
        fake_app.setApplicationIconImage_.assert_called_once_with(fake_image)

    def test_skips_when_image_load_fails(self, force_macos):
        # initByReferencingFile_ returns None for missing/invalid files —
        # don't pass None to setApplicationIconImage_.
        fake_app = mock.MagicMock()
        fake_image_class = mock.MagicMock()
        fake_image_class.alloc.return_value.initByReferencingFile_.return_value = None
        fake_appkit = mock.MagicMock()
        fake_appkit.NSApp = fake_app
        fake_appkit.NSImage = fake_image_class
        with mock.patch.dict(sys.modules, {"AppKit": fake_appkit}):
            macos.refresh_dock_icon("/missing.png")
        fake_app.setApplicationIconImage_.assert_not_called()

    def test_no_op_on_non_macos(self, force_non_macos):
        macos.refresh_dock_icon("/anywhere.png")  # must not raise


class TestSetLaunchAtLogin:
    def test_register_invokes_osascript_with_make_login_item(self, force_macos):
        with mock.patch("subprocess.run") as run:
            macos.set_launch_at_login(True, hidden=True)
        run.assert_called_once()
        args = run.call_args[0][0]
        assert args[0] == "osascript"
        script = args[2]
        assert "make login item" in script
        assert 'name:"dlwithit"' in script
        assert "hidden:true" in script

    def test_register_with_hidden_false(self, force_macos):
        with mock.patch("subprocess.run") as run:
            macos.set_launch_at_login(True, hidden=False)
        script = run.call_args[0][0][2]
        assert "hidden:false" in script

    def test_unregister_invokes_osascript_with_delete(self, force_macos):
        with mock.patch("subprocess.run") as run:
            macos.set_launch_at_login(False)
        script = run.call_args[0][0][2]
        assert "delete login item" in script
        assert '"dlwithit"' in script

    def test_no_op_on_non_macos(self, force_non_macos):
        with mock.patch("subprocess.run") as run:
            macos.set_launch_at_login(True)
            macos.set_launch_at_login(False)
        run.assert_not_called()

    def test_swallows_subprocess_failure(self, force_macos):
        with mock.patch("subprocess.run", side_effect=OSError("boom")):
            macos.set_launch_at_login(True)  # must not raise


class TestIsLaunchAtLoginEnabled:
    def test_true_when_dlwithit_in_login_items(self, force_macos):
        fake_result = mock.MagicMock(stdout="Notion, dlwithit, Slack")
        with mock.patch("subprocess.run", return_value=fake_result):
            assert macos.is_launch_at_login_enabled() is True

    def test_false_when_dlwithit_absent(self, force_macos):
        fake_result = mock.MagicMock(stdout="Notion, Slack")
        with mock.patch("subprocess.run", return_value=fake_result):
            assert macos.is_launch_at_login_enabled() is False

    def test_false_on_non_macos(self, force_non_macos):
        assert macos.is_launch_at_login_enabled() is False

    def test_false_on_subprocess_failure(self, force_macos):
        with mock.patch("subprocess.run", side_effect=OSError("boom")):
            assert macos.is_launch_at_login_enabled() is False


class TestBundlePath:
    def test_dev_fallback_when_not_frozen(self):
        with mock.patch.object(sys, "frozen", False, create=True):
            assert macos._bundle_path() == "/Applications/dlwithit.app"

    def test_walks_up_from_frozen_executable(self):
        fake_exe = "/Applications/dlwithit.app/Contents/MacOS/dlwithit"
        with mock.patch.object(sys, "frozen", True, create=True), \
             mock.patch.object(sys, "executable", fake_exe):
            assert macos._bundle_path() == "/Applications/dlwithit.app"
