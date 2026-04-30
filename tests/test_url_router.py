"""
Tests for core.url_router.classify_pasted_url — the routing logic for the
in-app paste-URL fallback. Pure URL inspection + yt-dlp ie.suitable().
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.url_router import classify_pasted_url


class TestEmptyAndInvalid:
    def test_empty_string(self):
        assert classify_pasted_url("") == "unsupported"

    def test_whitespace(self):
        assert classify_pasted_url("   ") == "unsupported"

    def test_none(self):
        assert classify_pasted_url(None) == "unsupported"

    def test_non_http_scheme(self):
        assert classify_pasted_url("ftp://example.com/x.mp4") == "unsupported"

    def test_file_url(self):
        assert classify_pasted_url("file:///tmp/x.mp4") == "unsupported"

    def test_no_netloc(self):
        assert classify_pasted_url("http:///nothing") == "unsupported"


class TestDirectImageURLs:
    @pytest.mark.parametrize("url", [
        "https://cdn.example.com/photo.jpg",
        "https://cdn.example.com/photo.jpeg",
        "https://cdn.example.com/photo.PNG",        # case-insensitive
        "http://cdn.example.com/photo.webp",
        "https://example.com/path/to/img.gif",
        "https://example.com/img.bmp",
        "https://example.com/img.tiff",
        "https://example.com/img.heic",
    ])
    def test_direct_image(self, url):
        assert classify_pasted_url(url) == "image"


class TestDirectVideoURLs:
    @pytest.mark.parametrize("url", [
        "https://cdn.example.com/clip.mp4",
        "https://cdn.example.com/CLIP.MP4",         # case-insensitive
        "https://cdn.example.com/clip.webm",
        "https://example.com/video.mov",
        "https://example.com/video.mkv",
        "https://example.com/stream.m3u8",
        "https://example.com/segment.ts",
    ])
    def test_direct_video(self, url):
        assert classify_pasted_url(url) == "video"


class TestPlatformVideoURLs:
    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://vimeo.com/123456789",
        "https://player.vimeo.com/video/123456789",
        "https://www.instagram.com/p/ABC123/",
        "https://www.tiktok.com/@user/video/1234567890",
    ])
    def test_platform_video(self, url):
        # yt-dlp extractors recognize these as video pages
        assert classify_pasted_url(url) == "video"


class TestUnsupportedPages:
    @pytest.mark.parametrize("url", [
        "https://example.com/article",
        "https://news.ycombinator.com/",
        "https://en.wikipedia.org/wiki/Apollo_11",
    ])
    def test_random_pages_are_unsupported(self, url):
        # No file extension match, no yt-dlp extractor match — paste flow
        # should bail out and tell the user to use the extension.
        assert classify_pasted_url(url) == "unsupported"


class TestEdgeCases:
    def test_url_with_query_string(self):
        # Query strings shouldn't affect extension detection
        assert classify_pasted_url(
            "https://cdn.example.com/clip.mp4?token=abc123"
        ) == "video"

    def test_url_with_trailing_whitespace(self):
        # Common when copy-pasting from emails / chat
        assert classify_pasted_url(
            "  https://cdn.example.com/photo.jpg  "
        ) == "image"

    def test_path_without_extension(self):
        # A URL like https://site.com/photo with no extension — can't tell
        assert classify_pasted_url("https://example.com/photo") == "unsupported"
