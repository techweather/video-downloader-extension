"""
Tests for which format yt-dlp is told to download.

The format string decides what lands on disk, so these pin it down: the
strings themselves for every quality setting.
"""

from core.downloader import build_format_string


class TestFormatString:
    """The selector strings for each quality setting."""

    def test_best_merges_best_video_and_non_ad_audio(self):
        assert build_format_string('best') == (
            'bestvideo+(bestaudio[language!$=-desc]/bestaudio)/best')

    def test_bestaudio_skips_audio_description_tracks(self):
        assert build_format_string('bestaudio') == (
            'bestaudio[language!$=-desc]/bestaudio/best')

    def test_worst(self):
        assert build_format_string('worst') == 'worstvideo+worstaudio/worst'

    def test_numeric_quality_caps_height(self):
        assert build_format_string('720') == (
            'bestvideo[height<=720]+(bestaudio[language!$=-desc]/bestaudio)'
            '/best[height<=720]')
