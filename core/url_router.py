"""
Classify a single pasted URL into one of: image, video, or unsupported.

Used by the in-app paste-URL fallback, which is the escape hatch for when
the browser extension isn't available (Safari/Edge/etc., URL came from
a non-browser source, extension misfired, etc.).

Page-level scanning (the extension's "Pick Images" flow) deliberately
stays in the extension because it requires in-page DOM context that a
single URL can't provide.
"""

from urllib.parse import urlparse


IMAGE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif", ".heic"}
)
DIRECT_VIDEO_EXTENSIONS = frozenset(
    {".mp4", ".webm", ".mov", ".mkv", ".avi", ".flv", ".m4v", ".m3u8", ".ts"}
)


def _path_extension(url):
    """Return the lowercased extension of a URL's path, or '' if none."""
    path = urlparse(url).path
    if "." not in path:
        return ""
    return "." + path.rsplit(".", 1)[-1].lower()


def classify_pasted_url(url):
    """Classify a single pasted URL.

    Returns one of:
      'image'       — direct image URL (download as-is)
      'video'       — direct video URL OR a yt-dlp-supported page
      'unsupported' — empty/non-http/unrecognized; user should use the
                      extension's Pick Images for page-scanning cases
    """
    if not url or not url.strip():
        return "unsupported"

    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "unsupported"

    ext = _path_extension(url)
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in DIRECT_VIDEO_EXTENSIONS:
        return "video"

    # Fall through to yt-dlp's extractor check for platform URLs
    # (YouTube, Vimeo, Instagram, TikTok, etc.). Generic is excluded so
    # we don't claim every URL is a video.
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            for ie in ydl._ies.values():
                if ie.ie_key() == "Generic":
                    continue
                if ie.suitable(url):
                    return "video"
    except Exception:
        pass

    return "unsupported"
