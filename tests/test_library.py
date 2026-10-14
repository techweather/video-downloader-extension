"""
Tests for core/library.py — the record of past downloads behind the Gallery.
"""

import threading

import pytest

from core.library import Library


@pytest.fixture
def lib(tmp_path):
    library = Library(tmp_path / 'library.sqlite3')
    yield library
    library.close()


def job(job_id, state='done', source='YouTube', finished_at=1.0, **extra):
    base = {'id': job_id, 'url': f'https://x/{job_id}', 'page_url': 'https://x', 'source': source,
            'kind': 'video', 'title': job_id, 'state': state, 'finished_at': finished_at,
            'created_at': 0.5, 'file_path': None}
    base.update(extra)
    return base


class TestLibrary:
    def test_records_finished_jobs_newest_first(self, lib):
        lib.record(job('a', finished_at=1))
        lib.record(job('b', finished_at=2))
        assert [e['id'] for e in lib.entries()] == ['b', 'a']

    def test_ignores_jobs_still_in_progress(self, lib):
        lib.record(job('a', state='downloading'))
        lib.record(job('b', state='cancelled'))
        assert lib.entries() == []

    def test_keeps_failed_and_skipped(self, lib):
        lib.record(job('f', state='failed', error='Private video'))
        lib.record(job('s', state='skipped'))
        assert {e['id'] for e in lib.entries()} == {'f', 's'}

    def test_recording_again_updates_in_place(self, lib):
        lib.record(job('a', state='failed'))
        lib.record(job('a', state='done'))
        entries = lib.entries()
        assert len(entries) == 1 and entries[0]['state'] == 'done'

    def test_filters_by_source_and_state(self, lib):
        lib.record(job('a', source='Vimeo'))
        lib.record(job('b', source='YouTube'))
        lib.record(job('c', source='Vimeo', state='failed'))
        assert {e['id'] for e in lib.entries(source='Vimeo')} == {'a', 'c'}
        assert [e['id'] for e in lib.entries(source='Vimeo', state='done')] == ['a']

    def test_exists_reflects_the_file_on_disk(self, lib, tmp_path):
        real = tmp_path / 'clip.mp4'
        real.write_bytes(b'x')
        lib.record(job('here', file_path=str(real)))
        lib.record(job('gone', file_path=str(tmp_path / 'deleted.mp4')))
        by_id = {e['id']: e for e in lib.entries()}
        assert by_id['here']['exists'] is True
        assert by_id['gone']['exists'] is False

    def test_remove_forgets_entry_but_keeps_file(self, lib, tmp_path):
        real = tmp_path / 'clip.mp4'
        real.write_bytes(b'x')
        lib.record(job('a', file_path=str(real)))
        assert lib.remove('a') is True
        assert lib.remove('a') is False
        assert lib.entries() == []
        assert real.exists()

    def test_sources_counts(self, lib):
        lib.record(job('a', source='Vimeo'))
        lib.record(job('b', source='Vimeo'))
        lib.record(job('c', source='YouTube'))
        assert lib.sources() == [{'source': 'Vimeo', 'count': 2}, {'source': 'YouTube', 'count': 1}]

    def test_survives_reopening(self, tmp_path):
        path = tmp_path / 'lib.sqlite3'
        first = Library(path)
        first.record(job('a'))
        first.close()
        second = Library(path)
        assert [e['id'] for e in second.entries()] == ['a']
        second.close()

    def test_safe_from_several_threads(self, lib):
        def writer(n):
            for i in range(20):
                lib.record(job(f'{n}-{i}', finished_at=i))
        threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(lib.entries(limit=1000)) == 80
