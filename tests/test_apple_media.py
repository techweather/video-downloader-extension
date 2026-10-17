"""
Tests for Apple product-page animations (core/apple_media.py, apple-media.js).

Apple's <video> elements play through blob: URLs; the page only names the
folder each animation lives in. The extension sends that folder and the app
tries Apple's file names in it. No test here touches the network — the CDN
answers are recorded from the live pages (2026-10-17) and faked.
"""

import json
import queue
import shutil
import subprocess
from pathlib import Path

import pytest
import requests

from core import apple_media
from core.apple_media import (
    AppleMediaNotFound, candidate_urls, folder_url, is_animation_folder,
    pick_best, probe_size, resolve,
)
from core.routing import route_picked_video

REPO = Path(__file__).resolve().parent.parent
MINI = 'https://www.apple.com/105/media/us/mac-mini/2024/58e5921e-f447-487a-a789-3452c23b8400/anim/ports/'
IMAC = 'https://www.apple.com/105/media/us/imac/2024/e1d50c6b-bc34-47bd-850d-379149b71fb8/anim/hero/'
NEO = 'https://www.apple.com/105/media/us/macbook-neo/2026/eee281c9-06d4-45d9-9a37-ef16ad413279/anim/'

# What Apple's CDN answered for these folders (file name -> bytes). Anything
# not listed was a 404.
RECORDED = {
    # mac-mini "ports": see-through, so no mp4 at all — only .mov and .webm.
    MINI: {'large_2x.mov': 2384832, 'large_2x.webm': 2293588, 'large.mov': 793141,
           'large.webm': 976154, 'medium_2x.mov': 1174322, 'medium_2x.webm': 1593845,
           'small_2x.mov': 901803, 'small_2x.webm': 1238219, 'small.mov': 260517},
    # iMac hero: every size, retina and not.
    IMAC: {'xlarge_2x.mp4': 2583183, 'xlarge.mp4': 2195845, 'large_2x.mp4': 2263129,
           'large.mp4': 1099971, 'medium_2x.mp4': 1768687, 'small.mp4': 717263,
           'xsmall_2x.mp4': 1407432, 'xsmall.mp4': 695259},
    # MacBook Neo "display": no retina copies, and a .webm beside each mp4.
    NEO + 'display/': {'xlarge.mp4': 11339082, 'xlarge.webm': 11321574,
                       'large.mp4': 9972568, 'small.mp4': 2851754},
    # MacBook Neo "performance": the webm is bigger than the mp4, but the mp4 wins.
    NEO + 'performance/': {'xlarge_2x.mp4': 15241572, 'xlarge_2x.webm': 15522897,
                           'xlarge.mp4': 14246225, 'large_2x.mp4': 12791835},
}


def recorded_probe(url, session=None, referer=None):
    folder, _, name = url.rpartition('/')
    return RECORDED.get(folder + '/', {}).get(name)


class TestFolders:
    def test_relative_basepath_resolves_against_the_page(self):
        assert folder_url('/105/media/us/mac-mini/2024/x/anim/ports/',
                          'https://www.apple.com/mac-mini/') == \
            'https://www.apple.com/105/media/us/mac-mini/2024/x/anim/ports/'

    def test_other_regions_keep_their_own_host(self):
        assert folder_url('/105/media/uk/imac/2024/x/anim/hero/', 'https://www.apple.com/uk/imac/') == \
            'https://www.apple.com/105/media/uk/imac/2024/x/anim/hero/'

    def test_no_page_falls_back_to_apple(self):
        assert folder_url('/105/media/us/imac/x/anim/hero') == \
            'https://www.apple.com/105/media/us/imac/x/anim/hero/'

    def test_recognises_animation_folders(self):
        assert is_animation_folder(MINI)
        assert not is_animation_folder(MINI + 'large_2x.mov')
        assert not is_animation_folder('https://example.com/anim/hero/')
        assert not is_animation_folder('https://www.apple.com/mac-mini/')
        assert not is_animation_folder(None)


class TestCandidates:
    def test_every_size_density_and_format_largest_first(self):
        urls = candidate_urls(IMAC)
        assert len(urls) == 5 * 2 * 3
        assert urls[:4] == [IMAC + 'xlarge_2x.mp4', IMAC + 'xlarge_2x.mov',
                            IMAC + 'xlarge_2x.webm', IMAC + 'xlarge.mp4']
        assert urls[-1] == IMAC + 'xsmall.webm'

    def test_mp4_beats_a_bigger_webm(self):
        sizes = {NEO + 'performance/xlarge_2x.mp4': 15241572,
                 NEO + 'performance/xlarge_2x.webm': 15522897}
        assert pick_best(sizes) == (NEO + 'performance/xlarge_2x.mp4', 15241572)

    def test_biggest_file_wins_within_a_format(self):
        sizes = {IMAC + 'large_2x.mp4': 2263129, IMAC + 'xlarge_2x.mp4': 2583183,
                 IMAC + 'xlarge.mp4': None}
        assert pick_best(sizes)[0] == IMAC + 'xlarge_2x.mp4'

    def test_mov_before_webm_when_there_is_no_mp4(self):
        sizes = {MINI + 'large_2x.webm': 9_000_000, MINI + 'large_2x.mov': 2384832}
        assert pick_best(sizes)[0] == MINI + 'large_2x.mov'

    def test_nothing_found(self):
        assert pick_best({IMAC + 'xlarge.mp4': None}) is None


class TestResolve:
    @pytest.mark.parametrize('folder, expected', [
        (MINI, 'large_2x.mov'),
        (IMAC, 'xlarge_2x.mp4'),
        (NEO + 'display/', 'xlarge.mp4'),       # no _2x copies at all
        (NEO + 'performance/', 'xlarge_2x.mp4'),
    ])
    def test_recorded_pages(self, folder, expected):
        url, size = resolve(folder, 'https://www.apple.com/', probe=recorded_probe)
        assert url == folder + expected
        assert size == RECORDED[folder][expected]

    def test_relative_basepath(self):
        url, _ = resolve('/105/media/us/imac/2024/e1d50c6b-bc34-47bd-850d-379149b71fb8/anim/hero/',
                         'https://www.apple.com/imac/', probe=recorded_probe)
        assert url == IMAC + 'xlarge_2x.mp4'

    def test_a_folder_with_nothing_in_it_is_a_clear_error(self):
        with pytest.raises(AppleMediaNotFound, match="Couldn't find the video file"):
            resolve(NEO + 'gone/', probe=recorded_probe)


class FakeResponse:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.closed = False

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error:
            raise self.error
        return self.response


class TestProbe:
    def test_reads_the_total_from_a_range_reply(self):
        session = FakeSession(FakeResponse(206, {'Content-Range': 'bytes 0-0/15241572',
                                                 'Content-Type': 'video/mp4'}))
        assert probe_size(IMAC + 'xlarge_2x.mp4', session=session, referer='https://www.apple.com/imac/') == 15241572
        _, kwargs = session.calls[0]
        assert kwargs['headers']['Range'] == 'bytes=0-0'
        assert 'Safari' in kwargs['headers']['User-Agent']
        assert kwargs['headers']['Referer'] == 'https://www.apple.com/imac/'
        assert session.response.closed

    def test_server_without_ranges(self):
        session = FakeSession(FakeResponse(200, {'Content-Length': '2384832'}))
        assert probe_size(MINI + 'large_2x.mov', session=session) == 2384832

    @pytest.mark.parametrize('response', [
        FakeResponse(404, {'Content-Type': 'text/html'}),
        FakeResponse(200, {'Content-Type': 'text/html; charset=utf-8', 'Content-Length': '90000'}),
        FakeResponse(206, {'Content-Range': 'bytes 0-0/*'}),
    ])
    def test_no_file(self, response):
        assert probe_size(IMAC + 'xlarge.mp4', session=FakeSession(response)) is None

    def test_network_error_is_no_file(self):
        session = FakeSession(error=requests.ConnectionError('offline'))
        assert probe_size(IMAC + 'xlarge.mp4', session=session) is None


class TestRouting:
    def test_animation_is_a_direct_download_that_carries_its_folder(self):
        video = {'url': MINI, 'type': 'apple-anim', 'basepath': MINI, 'title': 'Mac mini - ports'}
        kind, payload = route_picked_video(video, 'https://www.apple.com/mac-mini/', 'www.apple.com')
        assert kind == 'direct'
        assert payload['apple_basepath'] == MINI
        assert payload['title'] == 'Mac mini - ports'
        assert payload['pageUrl'] == 'https://www.apple.com/mac-mini/'


class TestEngine:
    @pytest.fixture
    def engine(self, tmp_path):
        from core.engine import Engine
        from core.library import Library
        from tests.test_engine import MemorySettings
        eng = Engine(library=Library(tmp_path / 'lib.sqlite3'), settings_store=MemorySettings(), enrich=None)
        yield eng
        eng.library.close()

    def test_picked_animation_reaches_the_worker_with_its_folder(self, engine):
        pick = engine.submit({'type': 'video-list', 'pageUrl': 'https://www.apple.com/mac-mini/',
                              'pageTitle': 'Mac mini - Apple', 'source': 'www.apple.com',
                              'videos': [{'url': MINI, 'type': 'apple-anim', 'basepath': MINI,
                                          'title': 'Mac mini - ports'}]})
        [job_id] = engine.resolve_pick(pick['pick_id'], [0])
        [item] = list(engine.download_queue.queue)
        assert item['type'] == 'direct-video'
        assert item['apple_basepath'] == MINI
        assert engine.get_job(job_id)['source'] == 'apple.com'

    def test_the_file_found_replaces_the_folder_url(self, engine):
        job_id = engine.submit({'type': 'direct-video', 'url': MINI, 'apple_basepath': MINI,
                                'pageUrl': 'https://www.apple.com/mac-mini/'})['job_id']
        engine._on_status(job_id, f'resolved_url:{MINI}large_2x.mov')
        assert engine.get_job(job_id)['url'] == MINI + 'large_2x.mov'


class FakeDownload:
    """Stands in for the streamed requests.get() of the real file."""

    def __init__(self, body, headers=None, status=200):
        self.body, self.status_code = body, status
        self.headers = headers if headers is not None else {'Content-Length': str(len(body)),
                                                             'Content-Type': 'video/quicktime'}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'{self.status_code} error')

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i + chunk_size]


def run_worker(item, monkeypatch, response, resolved=None):
    """Run one direct-video item through DownloadWorker.run() with the network faked."""
    from core import downloader
    from core.downloader import DownloadWorker

    fetched = []

    def fake_get(url, **kwargs):
        fetched.append(url)
        return response

    monkeypatch.setattr(downloader.requests, 'get', fake_get)
    monkeypatch.setattr(downloader, 'file_needs_encoding', lambda path: False)
    if resolved:
        monkeypatch.setattr(downloader.apple_media, 'resolve',
                            lambda basepath, page_url=None: (resolved, 1))
    q = queue.Queue()
    worker = DownloadWorker(q)
    events = []
    worker.status_update.connect(lambda i, s: events.append(('status', s)))
    worker.download_complete.connect(lambda i, p: events.append(('done', p)))
    worker.download_error.connect(lambda i, e: events.append(('error', e)))
    q.put(item)
    q.put(None)
    worker.run()
    return events, fetched


# A minimal QuickTime header: a 'ftyp' box, which is all the start of a real .mov needs.
MOV_BYTES = b'\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  ' + b'\x00' * 2000


class TestDownload:
    def item(self, tmp_path, **extra):
        item = {'id': 'job1', 'type': 'direct-video', 'url': MINI, 'title': 'Mac mini - ports',
                'referrer': 'https://www.apple.com/mac-mini/', 'save_path': str(tmp_path),
                'organize_by_platform': False, 'metadata_option': 'none',
                'encode_vp9': True, 'keep_original': False, 'apple_basepath': MINI}
        item.update(extra)
        return item

    def test_downloads_the_file_it_found(self, tmp_path, monkeypatch):
        events, fetched = run_worker(self.item(tmp_path), monkeypatch,
                                     FakeDownload(MOV_BYTES), resolved=MINI + 'large_2x.mov')
        assert fetched == [MINI + 'large_2x.mov']
        assert ('status', f'resolved_url:{MINI}large_2x.mov') in events
        done = [p for kind, p in events if kind == 'done']
        assert done == [str(tmp_path / 'Mac mini - ports.mov')]
        assert Path(done[0]).read_bytes() == MOV_BYTES

    def test_nothing_found_is_reported_not_saved(self, tmp_path, monkeypatch):
        from core import downloader

        def not_found(basepath, page_url=None):
            raise AppleMediaNotFound("Couldn't find the video file for this animation.")

        monkeypatch.setattr(downloader.apple_media, 'resolve', not_found)
        events, fetched = run_worker(self.item(tmp_path), monkeypatch, FakeDownload(MOV_BYTES))
        assert fetched == []
        assert any(kind == 'error' and "Couldn't find the video file" in e for kind, e in events)
        assert list(tmp_path.iterdir()) == []


# The <video> elements of the recorded pages, reduced to what apple-media.js reads.
PAGE_ELEMENTS = [
    {'id': 'design-video', 'data-video-basepath': '/105/media/us/mac-mini/2024/58e5921e-f447-487a-a789-3452c23b8400/anim/ports/'},
    {'id': 'welcome-hero-video', 'data-inline-media-basepath': '/105/media/us/mac-mini/2026/2140fd43-1461-420d-942c-6f254535a9a4/anim/hero/',
     'data-inline-media-retina-enabled': 'true'},
    # The same folder twice (Apple reuses an animation in two places).
    {'id': 'again', 'data-inline-media-basepath': '/105/media/us/mac-mini/2026/2140fd43-1461-420d-942c-6f254535a9a4/anim/hero/'},
    {'id': 'broken', 'data-video-basepath': 'blob:https://www.apple.com/1234'},
    {'id': 'empty', 'data-video-basepath': ''},
]

# Runs apple-media.js in node against a stand-in document.
NODE_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');
const [file, elementsJson] = process.argv.slice(1);
const elements = JSON.parse(elementsJson).map(attrs => ({
  getAttribute: name => (name in attrs ? attrs[name] : null),
  hasAttribute: name => name in attrs,
  parentElement: null,
}));
const doc = { title: 'Mac mini - Apple', querySelectorAll: () => elements };
const sandbox = { window: {}, document: doc, URL };
sandbox.window.location = { href: 'https://www.apple.com/mac-mini/' };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(file, 'utf8'), sandbox);
console.log(JSON.stringify(sandbox.window.__dlwithitScanAppleMedia(doc, 'https://www.apple.com/mac-mini/')));
"""


@pytest.mark.skipif(shutil.which('node') is None, reason='needs node')
class TestExtensionScan:
    def scan(self, elements=PAGE_ELEMENTS):
        out = subprocess.run(['node', '-e', NODE_HARNESS,
                              str(REPO / 'extension_chrome' / 'apple-media.js'), json.dumps(elements)],
                             capture_output=True, text=True, check=True, timeout=30)
        return json.loads(out.stdout)

    def test_both_extensions_ship_the_same_file(self):
        assert (REPO / 'extension_chrome' / 'apple-media.js').read_text() == \
            (REPO / 'extension_minimal' / 'apple-media.js').read_text()

    def test_finds_each_animation_folder_once(self):
        result = self.scan()
        assert result['folders'] == [
            MINI,
            'https://www.apple.com/105/media/us/mac-mini/2026/2140fd43-1461-420d-942c-6f254535a9a4/anim/hero/',
        ]
        ports = result['videos'][0]
        assert ports['type'] == 'apple-anim'
        assert ports['url'] == ports['basepath'] == MINI
        assert ports['title'] == 'Mac mini - ports'

    def test_section_names_read_as_words(self):
        result = self.scan([{'data-video-basepath': '/105/media/us/macbook-neo/2026/x/anim/continuity-hero/'}])
        assert result['videos'][0]['title'] == 'Mac mini - continuity hero'

    def test_pages_without_animations(self):
        assert self.scan([]) == {'videos': [], 'folders': []}

    def test_the_folder_routes_like_the_app_expects(self):
        video = self.scan()['videos'][0]
        assert is_animation_folder(video['url'])
        kind, payload = route_picked_video(video, 'https://www.apple.com/mac-mini/', 'www.apple.com')
        assert (kind, payload['apple_basepath']) == ('direct', MINI)
