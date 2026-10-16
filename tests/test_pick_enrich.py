"""
Tests for core/pick_enrich.py and the engine filling in picker details.
No network: oEmbed answers are faked.
"""

import threading

from core.engine import Engine
from core.library import Library
from core.pick_enrich import enrich_video, fetch_oembed, oembed_endpoint
from tests.test_engine import MemorySettings


class FakeResponse:
    def __init__(self, status, data):
        self.status_code = status
        self._data = data

    def json(self):
        return self._data


def fake_get(status=200, data=None, raises=False):
    calls = []

    def get(url, params=None, timeout=None):
        calls.append((url, params))
        if raises:
            raise OSError('offline')
        return FakeResponse(status, data)
    get.calls = calls
    return get


class TestOembed:
    def test_endpoints(self):
        assert 'vimeo.com' in oembed_endpoint('https://player.vimeo.com/video/1')
        assert 'youtube.com' in oembed_endpoint('https://youtu.be/abc')
        assert oembed_endpoint('https://cdn.example/a.mp4') is None
        assert oembed_endpoint(None) is None

    def test_fetch_maps_fields(self):
        get = fake_get(data={'title': 'Petbarn POV', 'thumbnail_url': 'https://i.vimeocdn.com/t.jpg', 'duration': 30})
        assert fetch_oembed('https://player.vimeo.com/video/1', get=get) == {
            'title': 'Petbarn POV', 'thumbnail': 'https://i.vimeocdn.com/t.jpg', 'duration': 30}
        assert get.calls[0][1]['url'] == 'https://player.vimeo.com/video/1'

    def test_fetch_gives_up_quietly(self):
        assert fetch_oembed('https://vimeo.com/1', get=fake_get(status=404)) is None
        assert fetch_oembed('https://vimeo.com/1', get=fake_get(raises=True)) is None
        assert fetch_oembed('https://vimeo.com/1', get=fake_get(data={'title': ''})) is None
        assert fetch_oembed('https://cdn.example/a.mp4', get=fake_get(data={'title': 'x'})) is None


class TestEnrichVideo:
    def test_replaces_guessed_title_and_fills_gaps(self):
        video = {'url': 'https://vimeo.com/1', 'title': 'Page title', 'thumbnail': None}
        out = enrich_video(video, fetch=lambda url: {'title': 'Real', 'thumbnail': 't.jpg', 'duration': 12})
        assert out['title'] == out['original_title'] == 'Real'
        assert out['thumbnail'] == 't.jpg' and out['duration'] == 12
        assert video['title'] == 'Page title'          # input untouched

    def test_keeps_a_thumbnail_the_page_already_had(self):
        video = {'url': 'https://vimeo.com/1', 'thumbnail': 'mine.jpg'}
        out = enrich_video(video, fetch=lambda url: {'title': 'Real', 'thumbnail': 't.jpg'})
        assert out['thumbnail'] == 'mine.jpg'

    def test_nothing_found(self):
        assert enrich_video({'url': 'https://vimeo.com/1'}, fetch=lambda url: None) is None


class TestEngineEnrichment:
    def test_open_pick_gets_real_titles_in_the_background(self, tmp_path):
        answers = {'https://player.vimeo.com/video/1': 'First film',
                   'https://player.vimeo.com/video/2': 'Second film'}

        def fake_enrich(video):
            title = answers.get(video['url'])
            return dict(video, title=title, original_title=title, thumbnail='t.jpg') if title else None

        engine = Engine(library=Library(tmp_path / 'lib.sqlite3'), settings_store=MemorySettings(),
                        enrich=fake_enrich)
        both_done = threading.Event()

        def on_pick(pick):
            if {v['title'] for v in pick['videos']} == {'First film', 'Second film', 'mux clip'}:
                both_done.set()
        engine.pick_changed.connect(on_pick)

        engine.submit({'type': 'video-list', 'pageUrl': 'https://studio.example', 'pageTitle': 'Studio',
                       'videos': [{'url': 'https://player.vimeo.com/video/1', 'title': 'Studio'},
                                  {'url': 'https://player.vimeo.com/video/2', 'title': 'Studio'},
                                  {'url': 'https://stream.mux.com/x/high.mp4', 'title': 'mux clip'}]})
        assert both_done.wait(3)
        videos = engine.picks()[0]['videos']
        assert [v['title'] for v in videos] == ['First film', 'Second film', 'mux clip']  # order kept
        engine.library.close()

    def test_answering_the_pick_first_is_safe(self, tmp_path):
        release = threading.Event()

        def slow_enrich(video):
            release.wait(2)
            return dict(video, title='Late')

        engine = Engine(library=Library(tmp_path / 'lib.sqlite3'), settings_store=MemorySettings(),
                        enrich=slow_enrich)
        pick_id = engine.submit({'type': 'video-list', 'pageUrl': 'https://p',
                                 'videos': [{'url': 'https://vimeo.com/1'}]})['pick_id']
        engine.dismiss_pick(pick_id)
        release.set()
        assert engine.picks() == []
        engine.library.close()
