"""
Tests for picking the highest-resolution copy of an image.

Two halves:
- image-picker.js chooses, from a <picture> or srcset, the file for the
  widest screen at the highest density — not the one the browser chose for
  the current window. Its helpers run here in node (skipped without it).
- core/apple_media.largest_image() upgrades an Apple still (…_medium_2x.jpg)
  to the biggest copy Apple has, by trying each size. Network faked.
"""

import json
import queue
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import requests

from core.apple_media import largest_image

REPO = Path(__file__).resolve().parent.parent
PICKER = REPO / 'extension_chrome' / 'image-picker.js'
XRAY = 'https://www.apple.com/v/mac-studio/o/images/overview/design/internals/hw_elements_fans_xray__eur65p3f7oom_'

# Recorded 2026-10-17: the mac-studio internals x-ray has six copies, no xlarge.
XRAY_SIZES = {'large_2x.jpg': 178785, 'large.jpg': 72198, 'medium_2x.jpg': 100385,
              'medium.jpg': 41042, 'small_2x.jpg': 29409, 'small.jpg': 12025}


def xray_probe(url, session=None, referer=None):
    return XRAY_SIZES.get(url[len(XRAY):]) if url.startswith(XRAY) else None


class TestLargestAppleImage:
    def test_window_sized_copy_becomes_the_biggest(self):
        assert largest_image(XRAY + 'medium_2x.jpg', probe=xray_probe) == XRAY + 'large_2x.jpg'

    def test_lazy_placeholder_src_is_upgraded_too(self):
        assert largest_image(XRAY + 'large.jpg', probe=xray_probe) == XRAY + 'large_2x.jpg'

    def test_keeps_the_format(self):
        seen = []

        def probe(url, session=None, referer=None):
            seen.append(url)
            return None

        assert largest_image(XRAY + 'small.png', probe=probe) == XRAY + 'small.png'
        assert seen and all(u.endswith('.png') for u in seen)

    @pytest.mark.parametrize('url', [
        'https://example.com/images/hero_large.jpg',            # not Apple
        'https://www.apple.com/v/mac-studio/o/images/logo.png',  # not a sized name
        'https://www.apple.com/105/media/us/imac/x/anim/hero/',  # not an image
    ])
    def test_other_images_are_left_alone(self, url):
        def probe(*args, **kwargs):
            raise AssertionError('should not probe')
        assert largest_image(url, probe=probe) == url


class FakeImage:
    headers = requests.structures.CaseInsensitiveDict({'Content-Type': 'image/jpeg', 'Content-Length': '4'})
    status_code = 200

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):
        yield b'\xff\xd8\xff\xe0'


def test_image_download_saves_the_biggest_copy(tmp_path, monkeypatch):
    from core import downloader
    from core.downloader import DownloadWorker

    fetched = []
    monkeypatch.setattr(downloader.apple_media, 'largest_image',
                        lambda url, referer=None: XRAY + 'large_2x.jpg')
    monkeypatch.setattr(downloader.requests, 'get', lambda url, **kw: fetched.append(url) or FakeImage())
    worker = DownloadWorker(queue.Queue())
    statuses = []
    worker.status_update.connect(lambda i, s: statuses.append(s))
    path = worker.download_image(XRAY + 'medium_2x.jpg', 'job1', str(tmp_path), False,
                                 'https://www.apple.com/mac-studio/')
    assert fetched == [XRAY + 'large_2x.jpg']
    assert Path(path).name == 'hw_elements_fans_xray__eur65p3f7oom_large_2x.jpg'
    assert f'resolved_url:{XRAY}large_2x.jpg' in statuses


# ---- the picker's helpers, in node ----------------------------------------

def helper_source():
    text = PICKER.read_text()
    match = re.search(r'// ---- srcset helpers.*?\n(.*?)// ---- end srcset helpers ----', text, re.S)
    assert match, 'srcset helper markers missing from image-picker.js'
    return match.group(1)


# A stand-in <picture>: each source is {attrs}; the img is {attrs}.
NODE_HARNESS = r"""
const [helpers, casesJson] = process.argv.slice(1);
eval(helpers);
function el(attrs) {
  return { getAttribute: n => (n in attrs ? attrs[n] : null), hasAttribute: n => n in attrs };
}
const out = JSON.parse(casesJson).map(c => {
  if (c.srcset !== undefined) return largestFromSrcset(c.srcset);
  const sources = c.sources.map(el);
  const img = el(c.img || {});
  img.parentElement = { querySelectorAll: () => sources };
  return bestPictureSource(img);
});
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which('node') is None, reason='needs node')
class TestPickerHelpers:
    def run(self, *cases):
        out = subprocess.run(['node', '-e', NODE_HARNESS, helper_source(), json.dumps(cases)],
                             capture_output=True, text=True, check=True, timeout=30)
        return json.loads(out.stdout)

    def test_both_extensions_ship_the_same_picker(self):
        assert PICKER.read_text() == (REPO / 'extension_minimal' / 'image-picker.js').read_text()

    @pytest.mark.parametrize('srcset, url', [
        ('/a_large.jpg, /a_large_2x.jpg 2x', '/a_large_2x.jpg'),
        ('a.jpg 1x,b.jpg 2x', 'b.jpg'),                              # no space after the comma
        ('s.jpg 480w, m.jpg 1200w, l.jpg 800w', 'm.jpg'),
        ('https://res.cloudinary.com/x/w_400,h_300/a.jpg 1x, https://res.cloudinary.com/x/w_800,h_600/a.jpg 2x',
         'https://res.cloudinary.com/x/w_800,h_600/a.jpg'),           # commas inside URLs
        ('data:image/gif;base64,R0lGODlhAQABAHAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==', None),
        ('', None),
    ])
    def test_largest_srcset_entry(self, srcset, url):
        [result] = self.run({'srcset': srcset})
        assert (result['url'] if result else None) == url

    def test_apple_picture_gives_the_widest_screen_at_2x(self):
        # The x-ray picture as it is once the page has filled it in (live DOM, 2026-10-17).
        placeholder = {'data-empty': '', 'media': '(min-width:0px)',
                       'srcset': 'data:image/gif;base64,R0lGODlhAQABAHAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=='}
        sources = [placeholder] + [
            {'media': media, 'srcset': f'/v/x/{size}.jpg, /v/x/{size}_2x.jpg 2x'}
            for media, size in [('(max-width:734px)', 'small'), ('(max-width:1068px)', 'medium'),
                                ('(min-width:0px)', 'large')]]
        assert self.run({'sources': sources, 'img': {'src': '/v/x/large.jpg'}}) == ['/v/x/large_2x.jpg']

    def test_lazy_picture_falls_back_to_the_img_src(self):
        placeholder = {'data-empty': '', 'srcset': 'data:image/gif;base64,R0lGODlhAQABAAAAACw='}
        assert self.run({'sources': [placeholder], 'img': {'src': '/v/x/large.jpg'}}) == ['/v/x/large.jpg']

    def test_jpeg_beats_avif_at_the_same_size(self):
        sources = [{'type': 'image/avif', 'srcset': '/a.avif, /a_2x.avif 2x'},
                   {'type': 'image/jpeg', 'srcset': '/a.jpg, /a_2x.jpg 2x'}]
        assert self.run({'sources': sources}) == ['/a_2x.jpg']

    def test_bigger_avif_still_beats_a_smaller_jpeg(self):
        sources = [{'type': 'image/avif', 'srcset': '/a.avif, /a_2x.avif 2x'},
                   {'type': 'image/jpeg', 'srcset': '/a.jpg'}]
        assert self.run({'sources': sources}) == ['/a_2x.avif']

    def test_nothing_usable(self):
        assert self.run({'sources': [], 'img': {'src': 'data:image/gif;base64,AAAA'}}) == [None]
