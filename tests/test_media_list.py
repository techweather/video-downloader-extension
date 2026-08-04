"""
Tests for core.media_list — video-list de-duplication.

Covers the two ways duplicates reach the picker: one scan finding the same file
through several selectors, and a double-triggered scan sending the list twice.
"""

import pytest

from core.media_list import normalize_media_url, dedupe_videos, merge_video_lists


def v(url, title=None, thumbnail=None):
    """Build a minimal scraped-video dict."""
    return {'url': url, 'title': title, 'thumbnail': thumbnail, 'type': 'direct'}


class TestNormalizeMediaUrl:

    def test_identical_urls_match(self):
        url = 'https://cdn.example.com/clip.mp4'
        assert normalize_media_url(url) == normalize_media_url(url)

    def test_fragment_is_stripped(self):
        assert (normalize_media_url('https://cdn.example.com/clip.mp4#t=10')
                == normalize_media_url('https://cdn.example.com/clip.mp4'))

    def test_host_case_is_ignored(self):
        assert (normalize_media_url('https://CDN.Example.COM/clip.mp4')
                == normalize_media_url('https://cdn.example.com/clip.mp4'))

    def test_scheme_case_is_ignored(self):
        assert (normalize_media_url('HTTPS://cdn.example.com/clip.mp4')
                == normalize_media_url('https://cdn.example.com/clip.mp4'))

    def test_default_port_is_stripped(self):
        assert (normalize_media_url('https://cdn.example.com:443/clip.mp4')
                == normalize_media_url('https://cdn.example.com/clip.mp4'))
        assert (normalize_media_url('http://cdn.example.com:80/clip.mp4')
                == normalize_media_url('http://cdn.example.com/clip.mp4'))

    def test_non_default_port_is_kept(self):
        assert (normalize_media_url('https://cdn.example.com:8443/clip.mp4')
                != normalize_media_url('https://cdn.example.com/clip.mp4'))

    def test_query_string_is_significant(self):
        """Signed CDN URLs differ only in their query — must not collapse."""
        assert (normalize_media_url('https://cdn.example.com/c.mp4?sig=aaa')
                != normalize_media_url('https://cdn.example.com/c.mp4?sig=bbb'))

    def test_http_and_https_are_distinct(self):
        assert (normalize_media_url('http://cdn.example.com/clip.mp4')
                != normalize_media_url('https://cdn.example.com/clip.mp4'))

    def test_different_paths_are_distinct(self):
        assert (normalize_media_url('https://cdn.example.com/a.mp4')
                != normalize_media_url('https://cdn.example.com/b.mp4'))

    def test_blob_url_compares_raw(self):
        blob = 'blob:https://example.com/9f8a-1234'
        assert normalize_media_url(blob) == blob

    @pytest.mark.parametrize('bad', [None, '', '   ', 123, [], {}])
    def test_unusable_input_returns_none(self, bad):
        assert normalize_media_url(bad) is None


class TestDedupeVideos:

    def test_empty_list(self):
        assert dedupe_videos([]) == []

    def test_none_input(self):
        assert dedupe_videos(None) == []

    def test_unique_list_is_unchanged(self):
        videos = [v('https://e.com/a.mp4'), v('https://e.com/b.mp4')]
        assert dedupe_videos(videos) == videos

    def test_exact_duplicates_collapse(self):
        videos = [v('https://e.com/a.mp4'), v('https://e.com/a.mp4')]
        assert len(dedupe_videos(videos)) == 1

    def test_first_occurrence_wins(self):
        """Earlier passes carry real titles; later regex passes carry filenames."""
        videos = [
            v('https://e.com/a.mp4', title='Behind the Scenes', thumbnail='t.jpg'),
            v('https://e.com/a.mp4', title='a'),
        ]
        result = dedupe_videos(videos)
        assert len(result) == 1
        assert result[0]['title'] == 'Behind the Scenes'
        assert result[0]['thumbnail'] == 't.jpg'

    def test_video_and_source_child_collapse(self):
        """<video src> and its <source src> resolve to one file."""
        videos = [
            v('https://e.com/clip.mp4', title='Clip'),
            v('https://e.com/clip.mp4#t=0', title='Clip'),
        ]
        assert len(dedupe_videos(videos)) == 1

    def test_doubled_scan_collapses_to_original(self):
        """The reported bug: two parallel scans, list sent twice."""
        scan = [v('https://e.com/a.mp4'), v('https://e.com/b.mp4'), v('https://e.com/c.mp4')]
        assert len(dedupe_videos(scan + scan)) == 3

    def test_entries_without_url_are_dropped(self):
        videos = [v('https://e.com/a.mp4'), {'title': 'no url'}, v(None)]
        assert len(dedupe_videos(videos)) == 1

    def test_non_dict_entries_are_dropped(self):
        assert len(dedupe_videos([v('https://e.com/a.mp4'), 'nope', None])) == 1

    def test_order_is_preserved(self):
        videos = [v('https://e.com/c.mp4'), v('https://e.com/a.mp4'), v('https://e.com/b.mp4')]
        assert [x['url'] for x in dedupe_videos(videos)] == [
            'https://e.com/c.mp4', 'https://e.com/a.mp4', 'https://e.com/b.mp4'
        ]


class TestMergeVideoLists:

    def test_merging_identical_lists_adds_nothing(self):
        existing = [v('https://e.com/a.mp4'), v('https://e.com/b.mp4')]
        merged, added = merge_video_lists(existing, list(existing))
        assert added == []
        assert len(merged) == 2

    def test_only_new_entries_are_added(self):
        existing = [v('https://e.com/a.mp4')]
        incoming = [v('https://e.com/a.mp4'), v('https://e.com/b.mp4')]
        merged, added = merge_video_lists(existing, incoming)
        assert [x['url'] for x in added] == ['https://e.com/b.mp4']
        assert len(merged) == 2

    def test_incoming_is_deduped_against_itself(self):
        merged, added = merge_video_lists([], [v('https://e.com/a.mp4')] * 3)
        assert len(added) == 1
        assert len(merged) == 1

    def test_merge_into_empty(self):
        incoming = [v('https://e.com/a.mp4')]
        merged, added = merge_video_lists([], incoming)
        assert len(merged) == 1 and len(added) == 1

    def test_existing_list_is_not_mutated(self):
        existing = [v('https://e.com/a.mp4')]
        merge_video_lists(existing, [v('https://e.com/b.mp4')])
        assert len(existing) == 1
