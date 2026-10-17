"""
Finds the real video file behind an animation on an Apple product page.

Apple's overview pages (apple.com/imac/, /mac-mini/, …) never put the file
URL in the page. A <video> carries a folder instead —

    data-video-basepath="/105/media/us/mac-mini/2024/{uuid}/anim/ports/"
    data-inline-media-basepath="/105/media/us/imac/2024/{uuid}/anim/hero/"

— and the page's script adds a file name picked for the visitor's screen
("large_2x.mp4") and plays it through a blob: URL nobody else can fetch.

So the extension sends the folder, and this module tries the file names
Apple uses, keeping the best one that answers. Nothing here hard-codes a
product, year or uuid: Apple changes those every product cycle, but the file
naming has stayed the same.
"""

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests

# Apple's CDN answers browsers; a bare client can get an error page instead.
BROWSER_UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 '
              '(KHTML, like Gecko) Version/17 Safari/605.1.15')

# Largest screen first. Which sizes exist varies per animation.
VIEWPORTS = ('xlarge', 'large', 'medium', 'small', 'xsmall')
# Retina copies are "_2x". The page's retina hint isn't reliable, so try both.
DENSITIES = ('_2x', '')
# mp4 when there is one. Animations with a see-through background have no mp4:
# Safari plays the .mov (HEVC with alpha), other browsers the .webm (VP9 with alpha).
EXTENSIONS = ('mp4', 'mov', 'webm')

PROBE_TIMEOUT = 10
PROBE_WORKERS = 8


class AppleMediaNotFound(Exception):
    """None of the file names Apple uses answered for this animation."""


def is_animation_folder(url):
    """True for an Apple animation folder URL (apple.com/…/anim/<section>/), the kind the extension sends."""
    parts = urlparse(url or '')
    host = (parts.hostname or '').lower()
    return ((host == 'apple.com' or host.endswith('.apple.com'))
            and '/anim/' in parts.path and parts.path.endswith('/'))


def folder_url(basepath, page_url=None):
    """Absolute URL of an animation folder, always ending in '/'.

    The page gives it relative (/105/media/…), so it's resolved against the page
    — or apple.com when there's no page. Resolving against the wrong base is how
    an HTML error page ends up saved as a .mp4.
    """
    base = page_url if page_url and page_url.startswith('http') else 'https://www.apple.com/'
    url = urljoin(base, basepath.strip())
    return url if url.endswith('/') else url + '/'


def candidate_urls(folder):
    """Every file name to try in an animation folder, best first."""
    return [f'{folder}{viewport}{density}.{ext}'
            for viewport in VIEWPORTS
            for density in DENSITIES
            for ext in EXTENSIONS]


def probe_size(url, session=None, referer=None):
    """Size in bytes of the media file at url, or None if there isn't one.

    Asks for a single byte (Range: bytes=0-0), so trying dozens of names costs
    almost nothing. A web page in reply — Apple's 404 page, a redirect to the
    product page — counts as no file.
    """
    http = session or requests
    headers = {'User-Agent': BROWSER_UA, 'Range': 'bytes=0-0'}
    if referer:
        headers['Referer'] = referer
    try:
        response = http.get(url, headers=headers, timeout=PROBE_TIMEOUT, stream=True)
    except requests.RequestException:
        return None
    try:
        if response.status_code not in (200, 206):
            return None
        content_type = (response.headers.get('Content-Type') or '').lower()
        if content_type.startswith('text/') or 'html' in content_type:
            return None
        if response.status_code == 206:
            # "bytes 0-0/15241572"
            total = (response.headers.get('Content-Range') or '').rpartition('/')[2]
            return int(total) if total.isdigit() else None
        length = response.headers.get('Content-Length') or ''
        return int(length) if length.isdigit() else None
    finally:
        response.close()


def pick_best(sizes):
    """Choose from {url: size or None}: the preferred format first, then the biggest file.

    An mp4 beats a .mov/.webm of any size — if one exists, the animation isn't
    transparent and the mp4 is the copy that plays everywhere. Within a format,
    the biggest file is the highest resolution.
    """
    found = {url: size for url, size in sizes.items() if size}
    for ext in EXTENSIONS:
        of_ext = {url: size for url, size in found.items() if url.endswith('.' + ext)}
        if of_ext:
            best = max(of_ext, key=of_ext.get)
            return best, of_ext[best]
    return None


def resolve(basepath, page_url=None, probe=probe_size):
    """URL and size of the best file for an animation folder.

    Raises AppleMediaNotFound when no candidate answers.
    """
    folder = folder_url(basepath, page_url)
    candidates = candidate_urls(folder)
    with requests.Session() as session, ThreadPoolExecutor(PROBE_WORKERS) as pool:
        sizes = dict(zip(candidates, pool.map(
            lambda url: probe(url, session=session, referer=page_url), candidates)))
    best = pick_best(sizes)
    if best is None:
        raise AppleMediaNotFound(
            "Couldn't find the video file for this animation. Apple may have moved "
            f"it since the page loaded — reload the page and try again. ({folder})")
    return best
