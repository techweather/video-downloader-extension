"""
Helpers for de-duplicating scraped media lists.

The extension's page scan finds the same video through several different
selectors (a <video src>, its <source> child, a data-* attribute, an inline
script reference), and a double-triggered scan sends the whole list twice.
Both cases produce duplicate rows in the video picker. These helpers collapse
them by comparing normalized URLs.
"""

from urllib.parse import urlsplit, urlunsplit

# Ports that carry no meaning when present explicitly.
_DEFAULT_PORTS = {'http': '80', 'https': '443'}


def normalize_media_url(url):
    """Return a comparison key for a media URL, or None if it isn't usable.

    Lowercases the scheme and host, drops the fragment and any default port,
    and leaves the path and query untouched — signed CDN URLs carry meaning in
    their query string, so stripping it would collapse genuinely distinct files.
    """
    if not url or not isinstance(url, str):
        return None

    candidate = url.strip()
    if not candidate:
        return None

    try:
        parts = urlsplit(candidate)
    except ValueError:
        return None

    # Non-http schemes (blob:, data:) have no host to normalize — compare raw.
    if not parts.scheme or not parts.netloc:
        return candidate

    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()

    # Strip a redundant :80 / :443 so the two spellings compare equal.
    default_port = _DEFAULT_PORTS.get(scheme)
    if default_port and netloc.endswith(f':{default_port}'):
        netloc = netloc[: -(len(default_port) + 1)]

    path = parts.path or '/'

    return urlunsplit((scheme, netloc, path, parts.query, ''))


def dedupe_videos(videos):
    """Drop duplicate entries from a scraped video list, keeping first-seen order.

    The first occurrence wins because earlier scan passes carry richer metadata
    (a real title and thumbnail) than the later regex-based passes.
    """
    if not videos:
        return []

    seen = set()
    unique = []

    for video in videos:
        if not isinstance(video, dict):
            continue

        key = normalize_media_url(video.get('url'))
        if key is None:
            continue
        if key in seen:
            continue

        seen.add(key)
        unique.append(video)

    return unique


def merge_video_lists(existing, incoming):
    """Append only the entries of `incoming` not already present in `existing`.

    Used when a second scan lands while the picker for that page is still open.
    Returns (merged_list, added_entries).
    """
    merged = dedupe_videos(existing)
    seen = {normalize_media_url(v.get('url')) for v in merged}

    added = []
    for video in dedupe_videos(incoming):
        key = normalize_media_url(video.get('url'))
        if key in seen:
            continue
        seen.add(key)
        added.append(video)

    return merged + added, added
