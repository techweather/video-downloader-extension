"""
Tests for core/routing.py — which tool downloads each picked video.
"""

import pytest

from core.routing import route_picked_video, source_name

PAGE = 'https://studio.example/work'
SRC = 'studio.example'


class TestRoutePickedVideo:
    @pytest.mark.parametrize('url', [
        'https://vimeo.com/123',
        'https://player.vimeo.com/video/123',
        'https://www.youtube.com/watch?v=abc',
        'https://youtu.be/abc',
        'https://www.instagram.com/p/xyz/',
        'https://www.tiktok.com/@a/video/1',
        'https://cdn.example/stream/master.m3u8',
    ])
    def test_platform_pages_and_streams_go_to_ytdlp(self, url):
        kind, payload = route_picked_video({'url': url, 'type': 'direct'}, PAGE, SRC)
        assert kind == 'ytdlp'
        assert payload['type'] == 'video'
        assert payload['url'] == url

    def test_hls_type_goes_to_ytdlp(self):
        kind, _ = route_picked_video({'url': 'https://cdn.example/x', 'type': 'hls'}, PAGE, SRC)
        assert kind == 'ytdlp'

    @pytest.mark.parametrize('video', [
        {'url': 'https://cdn.example/a.mp4', 'type': 'direct'},
        {'url': 'https://cdn.example/a', 'type': 'mux'},
        {'url': 'https://cdn.example/a', 'type': 'video/webm'},
        {'url': 'https://cdn.example/a.mov', 'type': 'unknown-kind'},
        {'url': 'https://cdn.example/a.mp4?token=1', 'type': 'unknown-kind'},
    ])
    def test_plain_files_download_directly(self, video):
        kind, payload = route_picked_video(video, PAGE, SRC)
        assert kind == 'direct'
        assert 'type' not in payload
        assert payload['pageUrl'] == PAGE and payload['source'] == SRC

    def test_unknown_format_falls_back_to_ytdlp(self):
        kind, payload = route_picked_video(
            {'url': 'https://cdn.example/watch/9', 'type': 'mystery', 'title': 'Nine'}, PAGE, SRC)
        assert kind == 'ytdlp'
        assert payload['title'] == 'Nine'

    def test_missing_type_counts_as_direct(self):
        kind, _ = route_picked_video({'url': 'https://cdn.example/no-extension'}, PAGE, SRC)
        assert kind == 'direct'

    def test_platform_title_prefers_original_title(self):
        _, payload = route_picked_video(
            {'url': 'https://vimeo.com/1', 'title': 'Trimmed', 'original_title': 'Full title'}, PAGE, SRC)
        assert payload['title'] == 'Full title'

    def test_playlist_picks_skip_a_second_probe(self):
        _, payload = route_picked_video(
            {'url': 'https://vimeo.com/1', 'playlist_index': 4}, PAGE, SRC, from_playlist=True)
        assert payload['skip_playlist_detection'] is True
        assert payload['playlist_index'] == 4

    def test_page_picks_do_not_skip_the_probe(self):
        _, payload = route_picked_video({'url': 'https://vimeo.com/1'}, PAGE, SRC)
        assert 'skip_playlist_detection' not in payload

    def test_thumbnail_is_carried_through(self):
        _, payload = route_picked_video(
            {'url': 'https://cdn.example/a.mp4', 'thumbnail': 'https://cdn.example/t.jpg'}, PAGE, SRC)
        assert payload['thumbnail'] == 'https://cdn.example/t.jpg'


class TestSourceName:
    @pytest.mark.parametrize('url, name', [
        ('https://www.youtube.com/watch?v=1', 'YouTube'),
        ('https://youtu.be/1', 'YouTube'),
        ('https://player.vimeo.com/video/1', 'Vimeo'),
        ('https://www.instagram.com/p/1', 'Instagram'),
        ('https://archive.org/details/x', 'archive.org'),
        ('https://ia800.us.archive.org/x.mp4', 'archive.org'),
        ('https://www.andrewsiner.com/', 'andrewsiner.com'),
        ('', 'Web'),
        (None, 'Web'),
    ])
    def test_names(self, url, name):
        assert source_name(url) == name

    def test_lookalike_domain_is_not_matched(self):
        assert source_name('https://notyoutube.com/x') == 'notyoutube.com'
