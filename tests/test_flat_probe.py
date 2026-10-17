"""
Tests for the quick flat probe that opens the picker on pages full of embeds.

yt-dlp's `extract_flat='in_playlist'` lists a page's embedded players without
reading each one (0.7 s instead of 3-9 s for a dozen Vimeo embeds). The engine
fills in titles and thumbnails afterwards via oEmbed. No network: yt-dlp is faked.
"""

import pytest

from core import downloader
from core.downloader import DownloadWorker, flat_entries_usable, is_flat_playlist

SMUGGLE = '#__youtubedl_smuggle=%7B%22referer%22%3A+%22https%3A%2F%2Fexample.com%2F%22%7D'


def flat_entry(url, ie='Vimeo', **extra):
    """One entry the way extract_flat leaves it: a link, no title or thumbnail."""
    return dict({'_type': 'url', 'ie_key': ie, 'url': url}, **extra)


def flat_page(*entries):
    return {'_type': 'playlist', 'title': 'Portfolio', 'extractor_key': 'Generic',
            'entries': list(entries)}


VIMEO_PAGE = flat_page(
    flat_entry('https://player.vimeo.com/video/1?title=0' + SMUGGLE),
    flat_entry('https://player.vimeo.com/video/2?title=0' + SMUGGLE),
    flat_entry('https://player.vimeo.com/video/3?title=0' + SMUGGLE),
)

FULL_PAGE = {'_type': 'playlist', 'title': 'Portfolio', 'entries': [
    {'_type': 'video', 'id': '1', 'title': 'Showreel', 'url': 'https://player.vimeo.com/video/1'},
    {'_type': 'video', 'id': '2', 'title': 'XPS 13', 'url': 'https://player.vimeo.com/video/2'},
]}


class TestFlatListChecks:
    def test_flat_playlist_is_recognised(self):
        assert is_flat_playlist(VIMEO_PAGE)

    def test_fully_read_playlist_is_not_flat(self):
        assert not is_flat_playlist(FULL_PAGE)

    def test_single_video_is_not_flat(self):
        assert not is_flat_playlist({'_type': 'video', 'title': 'One'})

    def test_vimeo_and_youtube_embeds_are_usable(self):
        """The engine can look up their titles afterwards."""
        page = flat_page(flat_entry('https://player.vimeo.com/video/1'),
                         flat_entry('https://www.youtube.com/embed/dQw4w9WgXcQ', ie='Youtube'))
        assert flat_entries_usable(page)

    def test_hosts_without_oembed_need_a_full_read(self):
        """No way to fill in a title later, so don't show "Video 2" for good."""
        page = flat_page(flat_entry('https://player.vimeo.com/video/1'),
                         flat_entry('https://fast.wistia.net/embed/iframe/abc', ie='Wistia'))
        assert not flat_entries_usable(page)

    def test_entries_that_already_have_titles_are_usable(self):
        """YouTube playlists come back flat but titled."""
        page = flat_page(flat_entry('https://cdn.example/a', ie='X', title='A'),
                         flat_entry('https://cdn.example/b', ie='X', title='B'))
        assert flat_entries_usable(page)

    def test_one_entry_is_not_a_list(self):
        assert not flat_entries_usable(flat_page(flat_entry('https://vimeo.com/1')))

    def test_entry_without_a_link_is_unusable(self):
        page = flat_page(flat_entry('https://vimeo.com/1'), flat_entry(None))
        assert not flat_entries_usable(page)

    def test_unavailable_entries_are_ignored(self):
        """yt-dlp yields None for videos it couldn't list."""
        page = flat_page(flat_entry('https://vimeo.com/1'), None, flat_entry('https://vimeo.com/2'))
        assert flat_entries_usable(page)


class FakeYDL:
    """Stands in for yt_dlp.YoutubeDL: answers by whether extract_flat was asked for."""
    calls = []
    flat_answer = None
    full_answer = None

    def __init__(self, params):
        self.params = params

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        flat = self.params.get('extract_flat')
        FakeYDL.calls.append(flat)
        return FakeYDL.flat_answer if flat else FakeYDL.full_answer


@pytest.fixture
def fake_ydl(monkeypatch):
    FakeYDL.calls = []
    FakeYDL.flat_answer = FakeYDL.full_answer = None
    monkeypatch.setattr(downloader.yt_dlp, 'YoutubeDL', FakeYDL)
    return FakeYDL


@pytest.fixture
def worker():
    return DownloadWorker(download_queue=[])


class TestProbe:
    def test_usable_flat_list_skips_the_slow_read(self, worker, fake_ydl):
        fake_ydl.flat_answer, fake_ydl.full_answer = VIMEO_PAGE, FULL_PAGE
        assert worker._probe('https://example.com/', None) is VIMEO_PAGE
        assert fake_ydl.calls == ['in_playlist']

    def test_unusable_flat_list_falls_back_to_a_full_read(self, worker, fake_ydl):
        fake_ydl.flat_answer = flat_page(flat_entry('https://fast.wistia.net/embed/iframe/a', ie='Wistia'),
                                         flat_entry('https://fast.wistia.net/embed/iframe/b', ie='Wistia'))
        fake_ydl.full_answer = FULL_PAGE
        assert worker._probe('https://example.com/', None) is FULL_PAGE
        assert fake_ydl.calls == ['in_playlist', None]

    def test_page_with_one_embed_is_read_fully(self, worker, fake_ydl):
        """Everything after the probe expects a resolved video for a single embed."""
        fake_ydl.flat_answer = flat_page(flat_entry('https://player.vimeo.com/video/1'))
        fake_ydl.full_answer = FULL_PAGE
        assert worker._probe('https://example.com/', None) is FULL_PAGE

    def test_single_video_needs_only_one_read(self, worker, fake_ydl):
        """extract_flat='in_playlist' doesn't change a plain video, so reuse it."""
        video = {'_type': 'video', 'title': 'One', 'extractor_key': 'Youtube'}
        fake_ydl.flat_answer = video
        assert worker._probe('https://youtube.com/watch?v=x', None) is video
        assert fake_ydl.calls == ['in_playlist']

    def test_already_resolved_playlist_needs_only_one_read(self, worker, fake_ydl):
        """Instagram carousels come back fully read even when flat is asked for."""
        fake_ydl.flat_answer = FULL_PAGE
        assert worker._probe('https://instagram.com/p/x/', None) is FULL_PAGE
        assert fake_ydl.calls == ['in_playlist']

    def test_flat_off_reads_fully(self, worker, fake_ydl):
        """A video picked from the picker is read fully straight away."""
        fake_ydl.full_answer = FULL_PAGE
        assert worker._probe('https://player.vimeo.com/video/1', None, flat=False) is FULL_PAGE
        assert fake_ydl.calls == [None]


class TestPickerFromFlatList:
    def test_flat_entries_open_the_picker_with_clean_links(self, worker):
        emitted = []
        worker.playlist_detected.connect(lambda did, data: emitted.append(data))

        assert worker._emit_playlist_if_multi({'id': 'a', 'url': 'https://example.com/'}, VIMEO_PAGE)

        videos = emitted[0]['videos']
        assert [v['url'] for v in videos] == [
            'https://player.vimeo.com/video/1?title=0',
            'https://player.vimeo.com/video/2?title=0',
            'https://player.vimeo.com/video/3?title=0',
        ]
        # Placeholders until oEmbed answers; the engine replaces them.
        assert [v['title'] for v in videos] == ['Video 1', 'Video 2', 'Video 3']
        assert [v['playlist_index'] for v in videos] == [1, 2, 3]
        assert emitted[0]['pageTitle'] == 'Portfolio'
