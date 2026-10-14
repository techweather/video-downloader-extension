"""
Tests for core/engine.py — job state, picks and settings.

The workers are never started: tests play the worker's part by emitting its
signals directly, so nothing is downloaded.
"""

import pytest

from core.engine import Engine, EngineError
from core.library import Library


class MemorySettings:
    """Stands in for config.settings.Settings without touching ~/.dlwithit_settings.json."""

    def __init__(self, initial=None):
        self.data = dict(initial or {})

    def load(self):
        return dict(self.data)

    def save(self, settings):
        self.data = dict(settings)


@pytest.fixture
def store():
    return MemorySettings({'window_geometry': {'x': 1}})


@pytest.fixture
def engine(tmp_path, store):
    eng = Engine(library=Library(tmp_path / 'lib.sqlite3'), settings_store=store)
    eng.events = []
    eng.job_changed.connect(lambda j: eng.events.append(('job', j['id'], j['state'])))
    eng.job_removed.connect(lambda i: eng.events.append(('removed', i)))
    eng.pick_changed.connect(lambda p: eng.events.append(('pick', p['id'], len(p['videos']))))
    eng.pick_closed.connect(lambda i: eng.events.append(('pick_closed', i)))
    yield eng
    eng.library.close()


def queued_items(engine):
    return list(engine.download_queue.queue)


def video_payload(**extra):
    payload = {'type': 'video', 'url': 'https://www.youtube.com/watch?v=abc',
               'pageUrl': 'https://www.youtube.com/watch?v=abc', 'title': 'A video',
               'thumbnail': 'https://i.ytimg.com/a.jpg'}
    payload.update(extra)
    return payload


class TestSubmit:
    def test_video_becomes_a_queued_job(self, engine):
        result = engine.submit(video_payload())
        assert result['status'] == 'queued'
        job = engine.get_job(result['job_id'])
        assert job['state'] == 'queued'
        assert job['source'] == 'YouTube'
        assert job['title'] == 'A video'
        assert job['thumbnail'] == 'https://i.ytimg.com/a.jpg'
        assert engine.events == [('job', job['id'], 'queued')]

    def test_queue_item_carries_current_settings(self, engine, store):
        store.data.update(encode_vp9=False, metadata_option='sidecar',
                          use_custom_location=True, custom_location='/tmp/dl-here')
        engine.submit(video_payload())
        item = queued_items(engine)[0]
        assert item['encode_vp9'] is False
        assert item['metadata_option'] == 'sidecar'
        assert item['save_path'] == '/tmp/dl-here'
        assert item['type'] == 'video' and item['quality'] == 'best'
        assert item['referrer'] == 'https://www.youtube.com/watch?v=abc'

    def test_image_title_and_thumbnail_come_from_its_url(self, engine):
        result = engine.submit({'type': 'image', 'url': 'https://cdn.x/photos/sunset.jpg?w=2',
                                'pageUrl': 'https://www.instagram.com/p/1'})
        job = engine.get_job(result['job_id'])
        assert job['title'] == 'sunset.jpg'
        assert job['thumbnail'] == 'https://cdn.x/photos/sunset.jpg?w=2'
        assert job['source'] == 'Instagram'

    def test_direct_video_type(self, engine):
        result = engine.submit({'type': 'direct-video', 'url': 'https://cdn.x/a.mp4', 'title': 'Clip'})
        assert engine.get_job(result['job_id'])['kind'] == 'direct-video'
        assert queued_items(engine)[0]['type'] == 'direct-video'

    def test_extension_multi_embed_payload_is_passed_to_the_worker(self, engine):
        detected = [{'url': 'https://vimeo.com/1'}, {'url': 'https://vimeo.com/2'}]
        engine.submit(video_payload(detectedVideos=detected))
        assert queued_items(engine)[0]['detectedVideos'] == detected

    @pytest.mark.parametrize('bad', [None, [], {}, {'type': 'video'}, {'type': 'video-list', 'videos': []}])
    def test_refuses_requests_without_media(self, engine, bad):
        with pytest.raises(EngineError):
            engine.submit(bad)
        assert queued_items(engine) == []

    def test_ids_are_unique(self, engine):
        ids = {engine.submit(video_payload())['job_id'] for _ in range(50)}
        assert len(ids) == 50

    def test_jobs_newest_first(self, engine):
        a = engine.submit(video_payload(title='first'))['job_id']
        b = engine.submit(video_payload(title='second'))['job_id']
        assert [j['id'] for j in engine.jobs()] == [b, a]


class TestWorkerEvents:
    def test_full_download_lifecycle(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        w = engine.worker
        w.status_update.emit(job_id, 'Preparing...')
        assert engine.get_job(job_id)['state'] == 'preparing'
        w.status_update.emit(job_id, 'thumbnail:https://i.ytimg.com/b.jpg')
        assert engine.get_job(job_id)['thumbnail'] == 'https://i.ytimg.com/b.jpg'
        w.progress_update.emit(job_id, 40, '12 of 30 MB')
        job = engine.get_job(job_id)
        assert job['state'] == 'downloading' and job['progress'] == 0.4
        w.status_update.emit(job_id, 'merging')
        assert engine.get_job(job_id)['state'] == 'merging'
        w.download_complete.emit(job_id, '/nonexistent/a.mp4')
        job = engine.get_job(job_id)
        assert job['state'] == 'done' and job['file_path'] == '/nonexistent/a.mp4'
        assert job['progress'] == 1.0 and job['finished_at']
        assert [e['id'] for e in engine.library.entries()] == [job_id]

    def test_multi_file_result(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        engine.worker.download_complete.emit(job_id, '/x/first.mp4|MULTI|3 files')
        job = engine.get_job(job_id)
        assert job['file_path'] == '/x/first.mp4' and job['file_count'] == 3
        assert job['status_text'] == '3 files'

    def test_failure_keeps_short_and_full_error(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        engine.worker.download_error.emit(job_id, 'ERROR: [youtube] abc: Private video\nmore detail')
        job = engine.get_job(job_id)
        assert job['state'] == 'failed'
        assert job['error'] == 'This video is private'
        assert 'more detail' in job['error_detail']
        assert engine.library.entries()[0]['state'] == 'failed'

    def test_conversion_handoff(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        engine.worker.encoding_needed.emit(job_id, '/x/a.webm', False, {})
        job = engine.get_job(job_id)
        assert job['state'] == 'converting' and job['status_text'] == 'Waiting to convert…'
        assert engine.encoder.encoding_queue.get_nowait()['input_path'] == '/x/a.webm'
        engine.encoder.encoding_started.emit(job_id)
        engine.encoder.encoding_progress.emit(job_id, 50, 'Converting… 50%')
        job = engine.get_job(job_id)
        assert job['state'] == 'converting' and job['progress'] == 0.5
        engine.encoder.encoding_complete.emit(job_id, '/x/a_h264.mp4')
        assert engine.get_job(job_id)['file_path'] == '/x/a_h264.mp4'

    def test_conversion_error(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        engine.encoder.encoding_error.emit(job_id, 'ffmpeg exploded')
        job = engine.get_job(job_id)
        assert job['state'] == 'failed' and job['error'].startswith('Conversion:')

    def test_skipped_and_cancelled(self, engine):
        a = engine.submit(video_payload())['job_id']
        b = engine.submit(video_payload())['job_id']
        engine.worker.download_skipped.emit(a, 'File already exists', '/x/a.mp4')
        engine.worker.download_cancelled.emit(b)
        assert engine.get_job(a)['state'] == 'skipped'
        assert engine.get_job(a)['file_path'] == '/x/a.mp4'
        assert engine.get_job(b)['state'] == 'cancelled'

    def test_rapid_progress_is_throttled_but_kept(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        engine.worker.progress_update.emit(job_id, 1, 'a')     # state change: published
        for pct in range(2, 50):
            engine.worker.progress_update.emit(job_id, pct, 'b')
        published = [e for e in engine.events if e[0] == 'job' and e[1] == job_id]
        assert len(published) == 2                              # queued, then downloading
        assert engine.get_job(job_id)['progress'] == 0.49       # latest value still stored
        engine.worker.download_complete.emit(job_id, '/x/a.mp4')
        assert engine.events[-1] == ('job', job_id, 'done')     # state changes never wait

    def test_title_from_ytdlp_replaces_placeholder(self, engine):
        job_id = engine.submit_link('https://www.youtube.com/watch?v=abc')['job_id']
        assert engine.get_job(job_id)['title'] == 'https://www.youtube.com/watch?v=abc'
        engine.worker.status_update.emit(job_id, 'title:Real Title')
        assert engine.get_job(job_id)['title'] == 'Real Title'

    def test_events_for_unknown_jobs_are_ignored(self, engine):
        engine.worker.progress_update.emit('nope', 10, 'x')
        engine.worker.download_complete.emit('nope', '/x')
        assert engine.jobs() == []

    def test_playlist_turns_the_job_into_a_pick(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        engine.worker.playlist_detected.emit(job_id, {
            'videos': [{'url': 'https://vimeo.com/1', 'title': 'One', 'playlist_index': 1},
                       {'url': 'https://vimeo.com/2', 'title': 'Two', 'playlist_index': 2}],
            'pageTitle': 'Reel', 'pageUrl': 'https://studio.example', 'source': 'studio.example'})
        assert engine.get_job(job_id) is None
        assert ('removed', job_id) in engine.events
        [pick] = engine.picks()
        assert pick['from_playlist'] is True and pick['page_title'] == 'Reel'
        assert len(pick['videos']) == 2


class TestPicks:
    def video_list(self, *urls, page='https://studio.example'):
        return {'type': 'video-list', 'pageUrl': page, 'pageTitle': 'Studio',
                'source': 'studio.example',
                'videos': [{'url': u, 'type': 'direct', 'title': u.rsplit('/', 1)[-1]} for u in urls]}

    def test_video_list_opens_a_pick(self, engine):
        result = engine.submit(self.video_list('https://cdn.x/a.mp4', 'https://cdn.x/b.mp4'))
        assert result['status'] == 'pick'
        assert [p['id'] for p in engine.picks()] == [result['pick_id']]
        assert queued_items(engine) == []

    def test_second_scan_of_the_same_page_joins_the_open_pick(self, engine):
        first = engine.submit(self.video_list('https://cdn.x/a.mp4'))['pick_id']
        second = engine.submit(self.video_list('https://cdn.x/a.mp4', 'https://cdn.x/b.mp4'))['pick_id']
        assert first == second
        assert len(engine.picks()[0]['videos']) == 2

    def test_different_pages_get_their_own_picks(self, engine):
        engine.submit(self.video_list('https://cdn.x/a.mp4', page='https://one.example'))
        engine.submit(self.video_list('https://cdn.x/a.mp4', page='https://two.example'))
        assert len(engine.picks()) == 2

    def test_resolving_downloads_the_chosen_videos_with_the_right_tool(self, engine):
        pick_id = engine.submit(self.video_list(
            'https://cdn.x/a.mp4', 'https://vimeo.com/5', 'https://cdn.x/c.mp4'))['pick_id']
        job_ids = engine.resolve_pick(pick_id, [0, 1, 99])
        assert len(job_ids) == 2
        assert [i['type'] for i in queued_items(engine)] == ['direct-video', 'video']
        assert engine.picks() == []
        assert ('pick_closed', pick_id) in engine.events

    def test_resolving_twice_is_refused(self, engine):
        pick_id = engine.submit(self.video_list('https://cdn.x/a.mp4'))['pick_id']
        engine.resolve_pick(pick_id, [0])
        with pytest.raises(EngineError):
            engine.resolve_pick(pick_id, [0])

    def test_dismiss(self, engine):
        pick_id = engine.submit(self.video_list('https://cdn.x/a.mp4'))['pick_id']
        assert engine.dismiss_pick(pick_id) is True
        assert engine.dismiss_pick(pick_id) is False
        assert queued_items(engine) == []


class TestListActions:
    def test_clear_finished_keeps_active_and_library(self, engine):
        done = engine.submit(video_payload())['job_id']
        active = engine.submit(video_payload())['job_id']
        engine.worker.download_complete.emit(done, '/x/a.mp4')
        engine.worker.progress_update.emit(active, 10, '')
        assert engine.clear_finished() == [done]
        assert [j['id'] for j in engine.jobs()] == [active]
        assert [e['id'] for e in engine.library.entries()] == [done]

    def test_remove_refuses_active_jobs(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        with pytest.raises(EngineError):
            engine.remove(job_id)

    def test_cancel_marks_and_tells_both_workers(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        engine.cancel(job_id)
        assert engine.get_job(job_id)['status_text'] == 'Cancelling…'
        assert job_id in engine.worker.cancelled_downloads
        assert job_id in engine.encoder.cancelled_jobs

    def test_retry_requeues_with_fresh_settings(self, engine, store):
        job_id = engine.submit(video_payload())['job_id']
        engine.worker.download_error.emit(job_id, 'ERROR: boom')
        store.data['encode_vp9'] = False
        engine.retry(job_id)
        assert engine.get_job(job_id)['state'] == 'queued'
        retried = queued_items(engine)[-1]
        assert retried['id'] == job_id and retried['encode_vp9'] is False

    def test_retry_refuses_finished_jobs(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        engine.worker.download_complete.emit(job_id, '/x/a.mp4')
        with pytest.raises(EngineError):
            engine.retry(job_id)

    def test_convert_keeps_the_original(self, engine, tmp_path):
        clip = tmp_path / 'a.webm'
        clip.write_bytes(b'x')
        job_id = engine.submit(video_payload())['job_id']
        engine.worker.download_complete.emit(job_id, str(clip))
        engine.convert(job_id)
        job_item = engine.encoder.encoding_queue.get_nowait()
        assert job_item['keep_original'] is True
        assert engine.get_job(job_id)['state'] == 'converting'

    def test_convert_needs_the_file(self, engine):
        job_id = engine.submit(video_payload())['job_id']
        engine.worker.download_complete.emit(job_id, '/gone/a.webm')
        with pytest.raises(EngineError):
            engine.convert(job_id)

    def test_unknown_job_raises_keyerror(self, engine):
        with pytest.raises(KeyError):
            engine.cancel('missing')


class TestSettings:
    def test_defaults_and_save_path(self, engine):
        s = engine.get_settings()
        assert s['encode_vp9'] is True and s['metadata_option'] == 'none'
        assert s['save_path'].endswith('Downloads/dlwithit')

    def test_update_keeps_keys_the_engine_does_not_own(self, engine, store):
        engine.update_settings({'keep_original': True})
        assert store.data['keep_original'] is True
        assert store.data['window_geometry'] == {'x': 1}

    def test_custom_location(self, engine, tmp_path):
        s = engine.update_settings({'use_custom_location': True, 'custom_location': str(tmp_path)})
        assert s['save_path'] == str(tmp_path)

    @pytest.mark.parametrize('bad', [
        {'nope': True},
        {'metadata_option': 'everything'},
        {'encode_vp9': 'yes'},
        {'custom_location': 'relative/path'},
    ])
    def test_rejects_bad_values_without_saving(self, engine, store, bad):
        before = dict(store.data)
        with pytest.raises(EngineError):
            engine.update_settings(bad)
        assert store.data == before

    def test_rejects_a_file_as_save_location(self, engine, tmp_path):
        f = tmp_path / 'file.txt'
        f.write_text('x')
        with pytest.raises(EngineError):
            engine.update_settings({'custom_location': str(f)})


class TestSubmitLink:
    def test_unsupported_link_is_explained(self, engine):
        with pytest.raises(EngineError, match='Video Download'):
            engine.submit_link('not a url')

    def test_direct_image_link(self, engine):
        result = engine.submit_link('https://cdn.x/photo.png')
        assert engine.get_job(result['job_id'])['kind'] == 'image'
