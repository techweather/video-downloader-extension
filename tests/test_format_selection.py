"""
Tests for which format yt-dlp is told to download.

The format string decides what lands on disk, so these pin it down two ways:
the strings themselves, and — for archive.org — what yt-dlp's real format
selector picks when handed those strings. The selection tests run offline
against format lists copied from real archive.org items (sizes measured
2026-10-12), so no network and no downloads.
"""

import copy
import inspect

import pytest
import yt_dlp
from yt_dlp.extractor.archiveorg import ArchiveOrgIE

from core.downloader import ARCHIVE_ORG_FORMAT, build_format_string


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

    def test_archive_org_gets_its_own_rule(self):
        assert build_format_string('best', 'ArchiveOrg') == ARCHIVE_ORG_FORMAT

    @pytest.mark.parametrize('extractor_key', [None, 'Youtube', 'Vimeo', 'Instagram', 'Generic'])
    def test_other_sites_unchanged(self, extractor_key):
        assert build_format_string('best', extractor_key) == build_format_string('best')


# --- archive.org selection, offline -----------------------------------------

def _archive_item(*files):
    """An info dict shaped like yt-dlp's archive.org extractor output."""
    formats = []
    for i, (ext, width, height, size, source) in enumerate(files):
        formats.append({
            'format_id': str(i),
            'url': f'https://archive.org/download/item/file{i}.{ext}',
            'width': width,
            'height': height,
            'filesize': size,
            'protocol': 'https',
            'source_preference': 0 if source == 'original' else -1,
            'format_note': source,
        })
    return {
        'id': 'item',
        'title': 'item',
        'extractor': 'archive.org',
        'extractor_key': 'ArchiveOrg',
        'webpage_url': 'https://archive.org/details/item',
        'formats': formats,
        '_format_sort_fields': ('source',),
    }


def _select(info, format_str):
    """Run yt-dlp's real format selection on `info` without touching the network."""
    params = {'format': format_str, 'quiet': True, 'no_warnings': True,
              'simulate': True, 'check_formats': False}
    with yt_dlp.YoutubeDL(params) as ydl:
        return ydl.process_ie_result(copy.deepcopy(info), download=False)


GROWTH_OF_PLANTS = _archive_item(          # 200634_The_Growth_of_Plants
    ('mp3', None, None, 6_554_485, 'derivative'),
    ('mp4', 640, 480, 53_378_840, 'derivative'),
    ('mp4', None, None, 10_919_974_583, 'original'),
    ('mov', 4096, 3072, 94_535_739_091, 'original'),
)
HOLIDAY_IN_HAWAII = _archive_item(         # 202085_Holiday_In_Hawaii
    ('mp3', None, None, 21_091_406, 'derivative'),
    ('mp4', 640, 480, 168_652_626, 'derivative'),
    ('mp4', None, None, 35_021_234_840, 'original'),
    ('mov', 4096, 3072, 351_256_158_358, 'original'),
)
SYMPHONY_IN_MOTION = _archive_item(        # 202098_Symphony_In_Motion
    ('mp3', None, None, 8_287_959, 'derivative'),
    ('mp4', 640, 480, 65_850_291, 'derivative'),
    ('mov', 2048, 1536, 1_785_649_332, 'original'),
)
MASTER_HANDS = _archive_item(              # masterhandscomplete4kh264
    ('mp3', 0, 0, 22_929_531, 'derivative'),
    ('ogv', 400, 300, 144_042_076, 'derivative'),
    ('mp4', 640, 480, 198_019_134, 'derivative'),
    ('mov', 4096, 3072, 13_838_403_624, 'original'),
)
DESIGN_FOR_1956 = _archive_item(           # Designfo1956 — SD, no master
    ('mp3', 0, 0, 4_452_864, 'derivative'),
    ('mp4', 320, 240, 39_499_240, 'derivative'),
    ('ogv', 400, 304, 39_464_045, 'derivative'),
    ('mp4', 640, 480, 57_947_878, 'derivative'),
)

HD_ITEMS = [
    pytest.param(GROWTH_OF_PLANTS, '3', '1', id='growth-of-plants-94GB'),
    pytest.param(HOLIDAY_IN_HAWAII, '3', '1', id='holiday-in-hawaii-351GB'),
    pytest.param(SYMPHONY_IN_MOTION, '2', '1', id='symphony-in-motion-1.8GB'),
    pytest.param(MASTER_HANDS, '3', '2', id='master-hands-13.8GB'),
]


class TestArchiveOrgSelection:
    """archive.org items with HD film scans must not default to the master."""

    @pytest.mark.parametrize('info, master_id, web_copy_id', HD_ITEMS)
    def test_plain_best_picks_the_master(self, info, master_id, web_copy_id):
        # The bug, reproduced: proves these sample items behave like the real ones.
        chosen = _select(info, build_format_string('best'))
        assert chosen['format_id'] == master_id
        assert chosen['format_note'] == 'original'

    @pytest.mark.parametrize('info, master_id, web_copy_id', HD_ITEMS)
    def test_archive_org_rule_picks_the_web_copy(self, info, master_id, web_copy_id):
        chosen = _select(info, build_format_string('best', 'ArchiveOrg'))
        assert chosen['format_id'] == web_copy_id
        assert chosen['ext'] == 'mp4'
        assert chosen['height'] == 480
        assert chosen['filesize'] < 250_000_000

    def test_sd_item_still_gets_its_largest_mp4(self):
        chosen = _select(DESIGN_FOR_1956, build_format_string('best', 'ArchiveOrg'))
        assert chosen['format_id'] == '3'
        assert (chosen['ext'], chosen['height']) == ('mp4', 480)

    def test_never_swaps_a_video_for_its_audio_track(self):
        # No video web copy, only an mp3: fall back to the master rather than
        # hand someone a soundtrack when they asked for the film.
        audio_only_copy = _archive_item(
            ('mp3', None, None, 8_000_000, 'derivative'),
            ('mov', 4096, 3072, 90_000_000_000, 'original'),
        )
        chosen = _select(audio_only_copy, build_format_string('best', 'ArchiveOrg'))
        assert chosen['format_note'] == 'original'
        assert chosen['ext'] == 'mov'

    def test_extractor_still_labels_original_vs_derivative(self):
        # ARCHIVE_ORG_FORMAT keys on how yt-dlp's archive.org extractor labels
        # each file. If a yt-dlp update changes that, the rule silently stops
        # matching and downloads fall back to the master — so fail loudly here.
        source = inspect.getsource(ArchiveOrgIE)
        assert "'format_note': f.get('source')" in source, (
            "yt-dlp's archive.org extractor changed how it labels files — "
            "re-check ARCHIVE_ORG_FORMAT in core/downloader.py")
