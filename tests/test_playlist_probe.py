"""
Tests for the multi-video probe path.

Covers the two changes that stop a page full of embedded players from sitting
at "Preparing..." with no sign of life: progress reporting from the yt-dlp
logger, and detecting the playlist off the first extraction instead of running
a second identical one.
"""

import pytest

from core.downloader import YtDlpLogger, DownloadWorker


class TestLoggerProgress:
    """The logger is the only progress signal available during extraction."""

    def test_reports_each_playlist_item(self):
        seen = []
        log = YtDlpLogger(progress_callback=lambda i, t: seen.append((i, t)))

        log.debug('[download] Downloading item 1 of 12')
        log.debug('[download] Downloading item 2 of 12')

        assert seen == [(1, 12), (2, 12)]

    def test_ignores_unrelated_messages(self):
        seen = []
        log = YtDlpLogger(progress_callback=lambda i, t: seen.append((i, t)))

        log.debug('[vimeo] 534189244: Downloading webpage')
        log.debug('[generic] Extracting URL: https://example.com/')
        log.debug('[download] Downloading playlist: Andrew Siner')

        assert seen == []

    def test_no_callback_is_safe(self):
        YtDlpLogger().debug('[download] Downloading item 1 of 12')  # must not raise

    def test_callback_failure_never_breaks_the_download(self):
        def boom(index, total):
            raise RuntimeError('UI gone')

        YtDlpLogger(progress_callback=boom).debug('[download] Downloading item 1 of 3')

    def test_skip_detection_still_works(self):
        log = YtDlpLogger(progress_callback=lambda i, t: None)
        log.debug('[download] /tmp/clip.mp4 has already been downloaded')

        assert log.skipped is True
        assert log.skipped_filename == '/tmp/clip.mp4'

    def test_reset_clears_skip_state(self):
        log = YtDlpLogger()
        log.debug('[download] /tmp/clip.mp4 has already been downloaded')
        log.reset()

        assert log.skipped is False
        assert log.skipped_filename is None


class TestPlaylistDetection:
    """_emit_playlist_if_multi decides whether to show the picker."""

    @pytest.fixture
    def worker(self):
        w = DownloadWorker(download_queue=[])
        self.emitted = []
        w.playlist_detected.connect(lambda did, data: self.emitted.append((did, data)))
        return w

    def entry(self, vid, title, url=None, ie='Vimeo'):
        return {'id': vid, 'title': title, 'url': url, 'ie_key': ie}

    def test_single_video_is_not_a_playlist(self, worker):
        info = {'_type': 'video', 'title': 'One'}
        assert worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info) is False
        assert self.emitted == []

    def test_playlist_of_one_is_not_a_playlist(self, worker):
        info = {'_type': 'playlist', 'entries': [self.entry('1', 'One')]}
        assert worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info) is False

    def test_multiple_entries_raise_the_picker(self, worker):
        info = {
            '_type': 'playlist',
            'title': 'Andrew Siner',
            'entries': [self.entry('1', 'Showreel'), self.entry('2', 'XPS 13')],
        }
        assert worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info) is True

        download_id, data = self.emitted[0]
        assert download_id == 'a'
        assert data['pageTitle'] == 'Andrew Siner'
        assert [v['title'] for v in data['videos']] == ['Showreel', 'XPS 13']

    def test_skip_flag_suppresses_detection(self, worker):
        """A video already chosen from the picker must not re-open it."""
        info = {'_type': 'playlist', 'entries': [self.entry('1', 'A'), self.entry('2', 'B')]}
        download = {'id': 'a', 'url': 'u', 'skip_playlist_detection': True}

        assert worker._emit_playlist_if_multi(download, info) is False
        assert self.emitted == []

    def test_none_entries_are_skipped(self, worker):
        """yt-dlp yields None for unavailable videos."""
        info = {
            '_type': 'playlist',
            'entries': [self.entry('1', 'A'), None, self.entry('3', 'C')],
        }
        worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info)

        assert [v['title'] for v in self.emitted[0][1]['videos']] == ['A', 'C']

    def test_playlist_index_is_one_based(self, worker):
        info = {'_type': 'playlist', 'entries': [self.entry('1', 'A'), self.entry('2', 'B')]}
        worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info)

        assert [v['playlist_index'] for v in self.emitted[0][1]['videos']] == [1, 2]

    def test_smuggled_data_is_stripped_from_urls(self, worker):
        url = 'https://player.vimeo.com/video/9#__youtubedl_smuggle=%7B%22x%22%3A1%7D'
        info = {'_type': 'playlist', 'entries': [
            self.entry('9', 'A', url), self.entry('8', 'B', 'https://vimeo.com/8')]}
        worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info)

        assert self.emitted[0][1]['videos'][0]['url'] == 'https://player.vimeo.com/video/9'

    def test_double_question_marks_are_repaired(self, worker):
        url = 'https://player.vimeo.com/video/9?h=abc?autoplay=1'
        info = {'_type': 'playlist', 'entries': [
            self.entry('9', 'A', url), self.entry('8', 'B', 'https://vimeo.com/8')]}
        worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info)

        assert self.emitted[0][1]['videos'][0]['url'] == \
            'https://player.vimeo.com/video/9?h=abc&autoplay=1'

    def test_missing_url_falls_back_to_platform_pattern(self, worker):
        info = {'_type': 'playlist', 'entries': [
            self.entry('534189244', 'A', None, 'Vimeo'),
            self.entry('dQw4', 'B', None, 'Youtube')]}
        worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info)

        urls = [v['url'] for v in self.emitted[0][1]['videos']]
        assert urls == ['https://vimeo.com/534189244',
                        'https://www.youtube.com/watch?v=dQw4']

    def test_instagram_prefers_webpage_url(self, worker):
        """CDN urls make absurd filenames; the post URL is the useful one."""
        entries = [
            {'id': '1', 'title': 'A', 'ie_key': 'Instagram',
             'url': 'https://cdn.example/verylong.mp4',
             'webpage_url': 'https://instagram.com/p/ABC/'},
            {'id': '2', 'title': 'B', 'ie_key': 'Instagram',
             'url': 'https://cdn.example/other.mp4',
             'webpage_url': 'https://instagram.com/p/DEF/'},
        ]
        worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, {'_type': 'playlist', 'entries': entries})

        urls = [v['url'] for v in self.emitted[0][1]['videos']]
        assert urls == ['https://instagram.com/p/ABC/', 'https://instagram.com/p/DEF/']

    def test_untitled_entries_get_a_readable_placeholder(self, worker):
        """extract_flat and some extractors return no title at all."""
        info = {'_type': 'playlist', 'entries': [
            {'id': '1', 'url': 'https://vimeo.com/1', 'ie_key': 'Vimeo'},
            {'id': '2', 'url': 'https://vimeo.com/2', 'ie_key': 'Vimeo'}]}
        worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info)

        assert [v['title'] for v in self.emitted[0][1]['videos']] == ['Video 1', 'Video 2']

    def test_page_title_falls_back_to_a_count(self, worker):
        info = {'_type': 'playlist', 'entries': [self.entry('1', 'A'), self.entry('2', 'B')]}
        worker._emit_playlist_if_multi({'id': 'a', 'url': 'u'}, info)

        assert self.emitted[0][1]['pageTitle'] == 'Playlist (2 videos)'

    def test_source_is_the_page_hostname(self, worker):
        info = {'_type': 'playlist', 'entries': [self.entry('1', 'A'), self.entry('2', 'B')]}
        worker._emit_playlist_if_multi(
            {'id': 'a', 'url': 'https://andrewsiner.com/main/'}, info)

        assert self.emitted[0][1]['source'] == 'andrewsiner.com'
