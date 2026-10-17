"""
Tests for core/media_check.py — refusing error pages and cut-off files.

These are the "non-viewable .mp4" cases from Apple's iMac page: a web page
saved under a video name, or a download that stopped before the end.
"""

import pytest

from core.error_reporter import summarize_error
from core.media_check import BadDownload, check_download, container_of, is_web_page_type, looks_like_text
from tests.test_apple_media import FakeDownload, MOV_BYTES, run_worker

MP4_HEAD = b'\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41'
WEBM_HEAD = b'\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01'
HTML = b'<!DOCTYPE html>\n<html><head><title>Page Not Found - Apple</title></head></html>'


class TestContainer:
    @pytest.mark.parametrize('head, name', [
        (MP4_HEAD, 'iso'),
        (b'\x00\x00\x00\x08wide\x00\x00\x00\x00mdat', 'iso'),   # QuickTime .mov
        (WEBM_HEAD, 'matroska'),
        (b'OggS\x00\x02', 'ogg'),
        (b'RIFF\x00\x00\x00\x00AVI LIST', 'avi'),
        (b'FLV\x01\x05', 'flv'),
    ])
    def test_known_containers(self, head, name):
        assert container_of(head) == name

    def test_html_is_no_container(self):
        assert container_of(HTML) is None

    @pytest.mark.parametrize('head', [HTML, b'  <html>', b'{"error": "expired"}', b'Access denied', b''])
    def test_text(self, head):
        assert looks_like_text(head)

    def test_binary_is_not_text(self):
        assert not looks_like_text(bytes(range(256)))

    def test_web_page_content_types(self):
        assert is_web_page_type('text/html; charset=UTF-8')
        assert is_web_page_type('application/xhtml+xml')
        assert not is_web_page_type('video/mp4')
        assert not is_web_page_type(None)


class TestCheckDownload:
    def write(self, tmp_path, data):
        path = tmp_path / 'clip.mp4'
        path.write_bytes(data)
        return path

    def test_complete_video_passes(self, tmp_path):
        data = MP4_HEAD + b'\x00' * 500
        check_download(self.write(tmp_path, data), len(data), len(data))

    def test_size_unknown_passes(self, tmp_path):
        check_download(self.write(tmp_path, MP4_HEAD), len(MP4_HEAD), None)

    def test_cut_off_download(self, tmp_path):
        with pytest.raises(BadDownload, match=r'stopped early \(1\.0 MB of 2\.6 MB\)'):
            check_download(self.write(tmp_path, MP4_HEAD), 1_000_000, 2_583_183)

    def test_web_page_saved_as_video(self, tmp_path):
        with pytest.raises(BadDownload, match='web page instead of the video'):
            check_download(self.write(tmp_path, HTML), len(HTML), len(HTML))

    def test_unknown_binary_format_is_let_through(self, tmp_path):
        data = bytes(range(256)) * 4
        check_download(self.write(tmp_path, data), len(data), len(data))


class TestDirectDownload:
    """The direct-video path in DownloadWorker.run(), with the network faked."""

    def item(self, tmp_path):
        return {'id': 'job1', 'type': 'direct-video', 'url': 'https://www.apple.com/105/media/x/anim/hero/xlarge_2x.mp4',
                'title': 'iMac - hero', 'referrer': 'https://www.apple.com/imac/',
                'save_path': str(tmp_path), 'organize_by_platform': False,
                'metadata_option': 'none', 'encode_vp9': True, 'keep_original': False}

    def errors(self, events):
        return [e for kind, e in events if kind == 'error']

    def test_good_file_is_saved(self, tmp_path, monkeypatch):
        events, _ = run_worker(self.item(tmp_path), monkeypatch, FakeDownload(MOV_BYTES))
        assert [p for kind, p in events if kind == 'done'] == [str(tmp_path / 'iMac - hero.mp4')]

    def test_web_page_reply_is_refused_and_not_saved(self, tmp_path, monkeypatch):
        response = FakeDownload(HTML, {'Content-Type': 'text/html; charset=utf-8',
                                       'Content-Length': str(len(HTML))})
        events, _ = run_worker(self.item(tmp_path), monkeypatch, response)
        [error] = self.errors(events)
        assert summarize_error(error) == 'The site sent a web page, not the video — reload and retry'
        assert list(tmp_path.iterdir()) == []

    def test_web_page_with_a_video_content_type_is_still_refused(self, tmp_path, monkeypatch):
        response = FakeDownload(HTML, {'Content-Type': 'video/mp4', 'Content-Length': str(len(HTML))})
        events, _ = run_worker(self.item(tmp_path), monkeypatch, response)
        assert 'web page instead of the video' in self.errors(events)[0]
        assert list(tmp_path.iterdir()) == []

    def test_cut_off_file_is_refused_and_removed(self, tmp_path, monkeypatch):
        response = FakeDownload(MOV_BYTES, {'Content-Type': 'video/mp4', 'Content-Length': '2583183'})
        events, _ = run_worker(self.item(tmp_path), monkeypatch, response)
        [error] = self.errors(events)
        assert summarize_error(error) == 'The download stopped early — try again'
        assert list(tmp_path.iterdir()) == []

    def test_asks_for_an_uncompressed_reply_as_a_browser(self, tmp_path, monkeypatch):
        seen = []
        run_worker(self.item(tmp_path), monkeypatch, FakeDownload(MOV_BYTES), headers_seen=seen)
        [headers] = seen
        assert headers['Accept-Encoding'] == 'identity'   # so bytes received match Content-Length
        assert 'Mozilla/5.0' in headers['User-Agent']
        assert headers['Referer'] == 'https://www.apple.com/imac/'
