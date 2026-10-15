"""
Real titles, thumbnails and durations for videos in a picker.

When the extension finds several embedded players on a page, all it can see
is the iframe, so every video often arrives with the same guessed title and no
picture. Vimeo and YouTube both answer a small public oEmbed request with the
video's actual title and thumbnail, which is much quicker than a full yt-dlp
extraction. The engine calls enrich_videos() in the background after the
picker opens and updates it as answers come in.
"""

import requests

OEMBED_ENDPOINTS = (
    (('vimeo.com',), 'https://vimeo.com/api/oembed.json'),
    (('youtube.com', 'youtu.be'), 'https://www.youtube.com/oembed'),
)


def oembed_endpoint(url):
    """The oEmbed endpoint that knows about this link, or None."""
    for hosts, endpoint in OEMBED_ENDPOINTS:
        if any(host in (url or '') for host in hosts):
            return endpoint
    return None


def fetch_oembed(url, get=requests.get, timeout=5):
    """{'title', 'thumbnail', 'duration'} for a Vimeo/YouTube link, or None if unavailable."""
    endpoint = oembed_endpoint(url)
    if not endpoint:
        return None
    try:
        response = get(endpoint, params={'url': url, 'format': 'json'}, timeout=timeout)
        if response.status_code != 200:
            return None
        data = response.json()
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get('title'):
        return None
    return {
        'title': data.get('title'),
        'thumbnail': data.get('thumbnail_url'),
        'duration': data.get('duration'),
    }


def enrich_video(video, fetch=fetch_oembed):
    """A copy of one picker video with oEmbed details filled in, or None if nothing to add."""
    details = fetch(video.get('url'))
    if not details:
        return None
    updated = dict(video)
    # The platform's own title beats the extension's guess (often the page title).
    updated['title'] = details['title']
    updated['original_title'] = details['title']
    if not video.get('thumbnail') and details.get('thumbnail'):
        updated['thumbnail'] = details['thumbnail']
    if not video.get('duration') and details.get('duration'):
        updated['duration'] = details['duration']
    return updated
