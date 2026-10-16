"""
Decides how each video picked from a page or playlist gets downloaded.

Shared by the engine (native apps) and the Qt window, which used to carry two
copies of this logic in ui/main_window.py.
"""

from urllib.parse import urlparse

# Types from the extension that always mean a direct file download.
# Includes HTML MIME types (e.g. 'video/mp4' from <source type="...">)
# and extension-defined type strings.
DIRECT_TYPES = frozenset({
    'direct', 'srcset', 'data-attribute', 'script-json',
    'preload', 'mux', 'meta-tag',
    'video/mp4', 'video/webm', 'video/quicktime',
    'video/x-m4v', 'video/ogg', 'video/x-matroska',
})

PLATFORM_HOSTS = ('vimeo.com', 'youtube.com', 'youtu.be', 'instagram.com', 'tiktok.com')
DIRECT_VIDEO_SUFFIXES = ('.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v')

# Friendly names for the sites people download from most; anything else
# shows its bare hostname.
SOURCE_NAMES = {
    'youtube.com': 'YouTube', 'youtu.be': 'YouTube',
    'vimeo.com': 'Vimeo',
    'instagram.com': 'Instagram',
    'tiktok.com': 'TikTok',
    'archive.org': 'archive.org',
    'x.com': 'X', 'twitter.com': 'X',
    'reddit.com': 'Reddit',
}


def route_picked_video(video, page_url, source, from_playlist=False):
    """Turn one picked video into a download request.

    Returns (kind, payload): kind is 'ytdlp' (platform page or HLS stream,
    handled by yt-dlp) or 'direct' (a plain video file fetched as-is).
    from_playlist marks videos that came out of yt-dlp's own playlist probe,
    so the follow-up download doesn't probe for a playlist again.
    """
    url = video['url']
    video_type = video.get('type', 'direct')
    base = {
        'url': url,
        'pageUrl': page_url,
        'source': source,
        'thumbnail': video.get('thumbnail'),
    }

    is_platform = (video_type == 'hls' or url.endswith('.m3u8') or
                   any(host in url for host in PLATFORM_HOSTS))
    if is_platform:
        payload = dict(base, type='video',
                       title=video.get('original_title', video.get('title', 'Video')))
        if from_playlist:
            payload.update(skip_playlist_detection=True,
                           playlist_index=video.get('playlist_index'))
        return 'ytdlp', payload

    # Trust the extension's type field first; fall back to the URL's extension.
    is_direct_file = (
        video_type in DIRECT_TYPES or
        url.endswith(DIRECT_VIDEO_SUFFIXES) or
        any(ext in url.lower() for ext in ['.mp4?', '.webm?', '.mov?'])
    )
    if is_direct_file:
        return 'direct', dict(base, title=video.get('title', 'Video'))

    # Unknown format: let yt-dlp have a go as a last resort.
    payload = dict(base, type='video', title=video.get('title', 'Video'))
    if from_playlist:
        payload.update(skip_playlist_detection=True,
                       playlist_index=video.get('playlist_index'))
    return 'ytdlp', payload


def source_name(url):
    """Short display name for the site a URL belongs to ('YouTube', 'archive.org', 'example.com')."""
    host = (urlparse(url or '').hostname or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    for domain, name in SOURCE_NAMES.items():
        if host == domain or host.endswith('.' + domain):
            return name
    return host or 'Web'
