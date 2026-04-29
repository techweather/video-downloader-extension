"""
Tests for core.app_updater — pure version logic + AppVersionCheckWorker.run()
behavior under mocked urllib responses (404, network error, missing fields).

No network, no Qt event loop. The worker is invoked by calling .run() directly
so the QThread plumbing isn't exercised — that's intentional.
"""

import io
import json
import sys
import os
import urllib.error
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.app_updater import (
    parse_version,
    is_newer,
    AppVersionCheckWorker,
)


class TestParseVersion:
    def test_basic(self):
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_strips_v_prefix(self):
        assert parse_version("v1.2.3") == (1, 2, 3)

    def test_whitespace(self):
        assert parse_version("  1.0.0 ") == (1, 0, 0)

    def test_two_part(self):
        assert parse_version("2.5") == (2, 5)

    def test_four_part(self):
        assert parse_version("1.0.0.1") == (1, 0, 0, 1)

    def test_empty_string(self):
        assert parse_version("") is None

    def test_none(self):
        assert parse_version(None) is None

    def test_non_numeric(self):
        assert parse_version("1.2.beta") is None

    def test_pre_release_tag(self):
        # We deliberately don't try to parse pre-release suffixes — return None
        # rather than guess (is_newer treats None as "not newer", staying safe).
        assert parse_version("1.2.3-rc1") is None


class TestIsNewer:
    def test_newer_patch(self):
        assert is_newer("1.0.1", "1.0.0") is True

    def test_newer_minor(self):
        assert is_newer("1.1.0", "1.0.9") is True

    def test_newer_major(self):
        assert is_newer("2.0.0", "1.99.99") is True

    def test_equal(self):
        assert is_newer("1.0.0", "1.0.0") is False

    def test_older(self):
        assert is_newer("1.0.0", "1.0.1") is False

    def test_v_prefix_on_either_side(self):
        assert is_newer("v1.0.1", "1.0.0") is True
        assert is_newer("1.0.1", "v1.0.0") is True

    def test_unparseable_latest_is_safe(self):
        # If the API returns garbage, never claim an update is available.
        assert is_newer("garbage", "1.0.0") is False

    def test_unparseable_current_is_safe(self):
        assert is_newer("1.0.1", "garbage") is False

    def test_empty_latest(self):
        assert is_newer("", "1.0.0") is False


def _http_error(code):
    return urllib.error.HTTPError(
        url="http://x", code=code, msg="x", hdrs=None, fp=None
    )


def _fake_response(payload):
    """Build a context-manager-compatible fake urlopen response."""
    body = json.dumps(payload).encode()
    fake = mock.MagicMock()
    fake.__enter__.return_value.read.return_value = body
    fake.__exit__.return_value = False
    return fake


class TestAppVersionCheckWorker:
    """Drive the worker synchronously by calling .run() directly."""

    def _capture(self, worker):
        captured = {}
        worker.finished = mock.MagicMock()
        worker.finished.emit = lambda v, u: captured.update(version=v, url=u)
        return captured

    def test_404_no_releases_yet(self):
        """The repo has no releases — API returns 404 and we silently no-op."""
        worker = AppVersionCheckWorker()
        captured = self._capture(worker)
        with mock.patch("urllib.request.urlopen", side_effect=_http_error(404)):
            worker.run()
        assert captured == {"version": "", "url": ""}

    def test_other_http_error(self):
        worker = AppVersionCheckWorker()
        captured = self._capture(worker)
        with mock.patch("urllib.request.urlopen", side_effect=_http_error(500)):
            worker.run()
        assert captured == {"version": "", "url": ""}

    def test_network_error(self):
        worker = AppVersionCheckWorker()
        captured = self._capture(worker)
        with mock.patch("urllib.request.urlopen", side_effect=OSError("no network")):
            worker.run()
        assert captured == {"version": "", "url": ""}

    def test_successful_response(self):
        worker = AppVersionCheckWorker()
        captured = self._capture(worker)
        payload = {
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/techweather/video-downloader-extension/releases/tag/v1.2.0",
        }
        with mock.patch("urllib.request.urlopen", return_value=_fake_response(payload)):
            worker.run()
        assert captured["version"] == "1.2.0"
        assert "v1.2.0" in captured["url"]

    def test_response_missing_tag_name(self):
        worker = AppVersionCheckWorker()
        captured = self._capture(worker)
        with mock.patch("urllib.request.urlopen", return_value=_fake_response({"html_url": "x"})):
            worker.run()
        assert captured == {"version": "", "url": "x"}

    def test_response_missing_html_url(self):
        worker = AppVersionCheckWorker()
        captured = self._capture(worker)
        with mock.patch("urllib.request.urlopen", return_value=_fake_response({"tag_name": "v1.0.0"})):
            worker.run()
        assert captured == {"version": "1.0.0", "url": ""}
