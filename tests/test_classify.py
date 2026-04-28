"""
Tests for the /classify endpoint.

classify uses yt-dlp's ie.suitable() — pure regex/string matching, no network.
Fast, deterministic, safe to run any time.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.flask_server import FlaskServer


@pytest.fixture(scope="module")
def client():
    server = FlaskServer(port=5558, debug=False)
    with server.app.test_client() as c:
        yield c


def classify(client, url):
    resp = client.post('/classify', json={'url': url})
    assert resp.status_code == 200
    return resp.get_json()['supported']


# --- URLs that should be supported by yt-dlp ---

class TestSupportedURLs:
    def test_youtube_standard(self, client):
        assert classify(client, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ') is True

    def test_youtube_short_url(self, client):
        assert classify(client, 'https://youtu.be/dQw4w9WgXcQ') is True

    def test_youtube_shorts(self, client):
        # yt-dlp requires the standard 11-char video ID format
        assert classify(client, 'https://www.youtube.com/shorts/dQw4w9WgXcQ') is True

    def test_vimeo_direct(self, client):
        assert classify(client, 'https://vimeo.com/123456789') is True

    def test_vimeo_player(self, client):
        assert classify(client, 'https://player.vimeo.com/video/123456789') is True

    def test_instagram_post(self, client):
        assert classify(client, 'https://www.instagram.com/p/ABC123def/') is True

    def test_instagram_reel(self, client):
        assert classify(client, 'https://www.instagram.com/reel/ABC123def/') is True

    def test_tiktok_video(self, client):
        assert classify(client, 'https://www.tiktok.com/@username/video/1234567890123') is True

    def test_twitter_video(self, client):
        assert classify(client, 'https://twitter.com/user/status/1234567890123456789') is True

    def test_x_video(self, client):
        assert classify(client, 'https://x.com/user/status/1234567890123456789') is True


# --- URLs that should NOT be supported (handled by DOM scan / direct download) ---

class TestUnsupportedURLs:
    def test_direct_mp4(self, client):
        # Generic extractor is excluded from classify — direct files go through DOM scan
        assert classify(client, 'https://example.com/video.mp4') is False

    def test_direct_webm(self, client):
        assert classify(client, 'https://example.com/video.webm') is False

    def test_generic_webpage(self, client):
        assert classify(client, 'https://example.com/some-article') is False

    def test_mux_stream(self, client):
        # Mux streams are detected by the extension's DOM scan, not yt-dlp
        assert classify(client, 'https://stream.mux.com/ABCD1234/high.mp4') is False

    def test_cdn_mp4(self, client):
        assert classify(client, 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4') is False


# --- Edge cases ---

class TestClassifyEdgeCases:
    def test_empty_url(self, client):
        resp = client.post('/classify', json={'url': ''})
        assert resp.status_code == 200
        assert resp.get_json()['supported'] is False

    def test_missing_url_key(self, client):
        resp = client.post('/classify', json={})
        assert resp.status_code == 200
        assert resp.get_json()['supported'] is False

    def test_no_body(self, client):
        resp = client.post('/classify')
        # Should not crash — returns 400 or 415, not 500
        assert resp.status_code in (400, 415)

    def test_malformed_url(self, client):
        resp = client.post('/classify', json={'url': 'not-a-url-at-all'})
        assert resp.status_code == 200
        assert resp.get_json()['supported'] is False
