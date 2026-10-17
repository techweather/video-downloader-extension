"""
Checks that a directly downloaded video file is really a whole video.

Two failures used to end up on disk as a ".mp4" that wouldn't open:

- the server sent a web page (an error or login page) instead of the file;
- the download stopped early. An mp4 keeps its index (the moov box) at the
  end more often than not, so a cut-off file doesn't play at all.

check_download() catches both and says so in words people can act on.
"""

# Box types an ISO media file (mp4, mov, m4v, 3gp) can open with.
_ISO_BOXES = (b'ftyp', b'moov', b'mdat', b'free', b'skip', b'wide', b'pnot', b'uuid')


class BadDownload(Exception):
    """The file that arrived isn't a usable video. The message is fit to show the user."""


def container_of(head):
    """Name of the media container the first bytes of a file belong to, or None."""
    if len(head) >= 8 and head[4:8] in _ISO_BOXES:
        return 'iso'                    # mp4 / mov / m4v
    if head[:4] == b'\x1a\x45\xdf\xa3':
        return 'matroska'               # mkv / webm
    if head[:4] == b'OggS':
        return 'ogg'
    if head[:4] == b'RIFF' and head[8:12] == b'AVI ':
        return 'avi'
    if head[:3] == b'FLV':
        return 'flv'
    if head[:4] == b'\x00\x00\x01\xba':
        return 'mpeg-ps'
    if head[:1] == b'\x47' and (len(head) < 189 or head[188:189] == b'\x47'):
        return 'mpeg-ts'
    return None


def looks_like_text(head):
    """True when the bytes read as a web page or other text rather than media."""
    stripped = head.lstrip(b'\xef\xbb\xbf \t\r\n').lower()
    if stripped.startswith((b'<!doctype', b'<html', b'<?xml', b'<head', b'<body', b'{', b'[')):
        return True
    if not stripped:
        return True
    # Media is binary: plenty of control bytes. Text has almost none.
    sample = stripped[:512]
    binary = sum(1 for b in sample if b < 9 or 13 < b < 32)
    return binary == 0


def is_web_page_type(content_type):
    """True for a Content-Type that means a web page, not a file."""
    content_type = (content_type or '').lower()
    return content_type.startswith('text/html') or 'xhtml' in content_type


def check_download(path, received, expected=None):
    """Raise BadDownload unless the file at path is a complete media file.

    received: bytes written. expected: the server's Content-Length (None or 0
    when it didn't say). Files in a container this doesn't know are let
    through as long as they aren't text — better a rare odd format than a
    refused good download.
    """
    if expected and received < expected:
        raise BadDownload(
            f"The download stopped early ({_mb(received)} of {_mb(expected)}), so the video "
            "wouldn't play. Try again.")
    with open(path, 'rb') as f:
        head = f.read(1024)
    if container_of(head):
        return
    if looks_like_text(head):
        raise BadDownload(
            "The site sent a web page instead of the video file. The link may have expired — "
            "reload the page and try again.")


def _mb(size):
    return f'{size / 1_000_000:.1f} MB'
