"""
Tests for summarize_error() — the one-line error shown on a failed download.
"""

from core.error_reporter import summarize_error


def test_plain_ytdlp_error():
    assert summarize_error('ERROR: [vimeo] 123: Private video') == '123: Private video'


def test_error_inside_the_worker_report():
    raw = ('Exception Type: DownloadError\n'
           'Error Message: ERROR: [youtube] zzz: This video is unavailable\n\n'
           'Download Details:\n- URL: https://www.youtube.com/watch?v=zzz\n')
    assert summarize_error(raw) == 'zzz: This video is unavailable'


def test_ansi_codes_and_urls_are_cleaned():
    raw = '\x1b[0;31mERROR:\x1b[0m [generic] Unable to download https://x.example/a.mp4: 403'
    assert summarize_error(raw) == 'Unable to download URL 403'


def test_long_messages_are_shortened():
    out = summarize_error('ERROR: ' + 'x' * 200)
    assert len(out) == 56 and out.endswith('…')


def test_fallback_without_an_error_line():
    assert summarize_error('Traceback: something   broke') == 'something broke'


def test_empty():
    assert summarize_error('') == ''
    assert summarize_error(None) == ''
