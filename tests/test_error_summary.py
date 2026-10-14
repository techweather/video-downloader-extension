"""
Tests for summarize_error() — the one-line error shown on a failed download.
"""

from core.error_reporter import summarize_error


def test_plain_ytdlp_error():
    assert summarize_error('ERROR: [vimeo] 123: Something odd happened') == '123: Something odd happened'


def test_error_inside_the_worker_report():
    raw = ('Exception Type: DownloadError\n'
           'Error Message: ERROR: [youtube] zzz: This video is unavailable\n\n'
           'Download Details:\n- URL: https://www.youtube.com/watch?v=zzz\n')
    assert summarize_error(raw) == 'This video is unavailable'


def test_ansi_codes_and_urls_are_cleaned():
    raw = '\x1b[0;31mERROR:\x1b[0m [generic] Unable to fetch https://x.example/a.mp4: boom'
    assert summarize_error(raw) == 'Unable to fetch URL boom'


def test_long_messages_are_shortened():
    out = summarize_error('ERROR: ' + 'x' * 200)
    assert len(out) == 56 and out.endswith('…')


def test_fallback_without_an_error_line():
    assert summarize_error('Traceback: something   broke') == 'something broke'


def test_empty():
    assert summarize_error('') == ''
    assert summarize_error(None) == ''


def test_common_failures_read_as_plain_english():
    assert summarize_error('ERROR: Unsupported URL: https://x') == 'No downloadable video found on this page'
    assert summarize_error('ERROR: [vimeo] 1: The web client only works when logged-in.') == \
        'This video needs you to be logged in'
    assert summarize_error('ERROR: [vimeo] 1: Private video') == 'This video is private'
    assert summarize_error('requests.exceptions.HTTPError: 403 Client Error / HTTP Error 403') == \
        'The site refused the download (403)'
