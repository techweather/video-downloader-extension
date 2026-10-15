"""
Tests for the native app's /app/ endpoints in api/flask_server.py.

Uses a real Engine whose workers are never started, so jobs are created and
can be driven by emitting worker signals, but nothing downloads.
"""

import json

import pytest

from api.flask_server import FlaskServer, TOKEN_HEADER
from core.engine import Engine
from core.library import Library
from tests.test_engine import MemorySettings

TOKEN = 'test-token'
AUTH = {TOKEN_HEADER: TOKEN}


@pytest.fixture
def engine(tmp_path):
    eng = Engine(library=Library(tmp_path / 'lib.sqlite3'), settings_store=MemorySettings(), enrich=None)
    yield eng
    eng.library.close()


@pytest.fixture
def server(engine):
    return FlaskServer(port=5559, engine=engine, token=TOKEN, keepalive_seconds=0.05)


@pytest.fixture
def client(server):
    return server.app.test_client()


def add_video(client, url='https://www.youtube.com/watch?v=abc'):
    return client.post('/download', json={'type': 'video', 'url': url, 'pageUrl': url, 'title': 'T'})


class TestAccess:
    @pytest.mark.parametrize('path', ['/app/state', '/app/jobs', '/app/settings', '/app/library'])
    def test_token_required(self, client, path):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={TOKEN_HEADER: 'wrong'}).status_code == 401
        assert client.get(path, headers=AUTH).status_code == 200

    def test_app_routes_have_no_cors(self, client):
        r = client.get('/app/state', headers=dict(AUTH, Origin='https://evil.example'))
        assert 'Access-Control-Allow-Origin' not in r.headers
        pre = client.options('/app/settings', headers={
            'Origin': 'https://evil.example', 'Access-Control-Request-Method': 'PATCH'})
        assert 'Access-Control-Allow-Origin' not in pre.headers

    @pytest.mark.parametrize('path', ['/health', '/'])
    def test_extension_routes_keep_cors(self, client, path):
        r = client.get(path, headers={'Origin': 'chrome-extension://abc'})
        assert r.headers.get('Access-Control-Allow-Origin') == 'chrome-extension://abc'

    def test_download_keeps_cors(self, client):
        r = client.post('/download', json={'type': 'image', 'url': 'https://x/a.png'},
                        headers={'Origin': 'chrome-extension://abc'})
        assert r.headers.get('Access-Control-Allow-Origin') == 'chrome-extension://abc'

    def test_without_engine_app_routes_are_unavailable(self):
        qt_mode = FlaskServer(port=5559).app.test_client()
        assert qt_mode.get('/app/state', headers=AUTH).status_code == 503

    def test_health_reports_engine(self, client):
        data = client.get('/health').get_json()
        assert data['engine'] is True and data['version']


class TestExtensionIntoEngine:
    def test_download_creates_a_job(self, client, engine):
        r = add_video(client)
        assert r.status_code == 200 and r.get_json()['status'] == 'queued'
        assert len(engine.jobs()) == 1

    def test_video_list_opens_a_pick_but_tells_the_extension_queued(self, client, engine):
        r = client.post('/download', json={'type': 'video-list', 'pageUrl': 'https://p', 'pageTitle': 'P',
                                           'videos': [{'url': 'https://cdn/a.mp4'}]})
        assert r.get_json()['status'] == 'queued'
        assert len(engine.picks()) == 1

    def test_bad_request_is_400(self, client):
        assert client.post('/download', json={'type': 'video'}).status_code == 400


class TestJobs:
    def test_state_snapshot(self, client):
        add_video(client)
        data = client.get('/app/state', headers=AUTH).get_json()
        assert len(data['jobs']) == 1
        assert set(data) >= {'jobs', 'picks', 'settings', 'version', 'ytdlp_version'}

    def test_paste_link(self, client):
        r = client.post('/app/jobs', json={'url': 'https://cdn.x/photo.jpg'}, headers=AUTH)
        assert r.status_code == 200 and r.get_json()['status'] == 'queued'

    def test_paste_unsupported_link_explains(self, client):
        r = client.post('/app/jobs', json={'url': 'nonsense'}, headers=AUTH)
        assert r.status_code == 400 and 'extension' in r.get_json()['error']

    def test_cancel_retry_flow(self, client, engine):
        job_id = add_video(client).get_json()['job_id']
        r = client.post(f'/app/jobs/{job_id}/cancel', headers=AUTH)
        assert r.get_json()['status_text'] == 'Cancelling…'
        engine.worker.download_cancelled.emit(job_id)
        r = client.post(f'/app/jobs/{job_id}/retry', headers=AUTH)
        assert r.get_json()['state'] == 'queued'

    def test_refused_action_is_400(self, client):
        job_id = add_video(client).get_json()['job_id']
        r = client.post(f'/app/jobs/{job_id}/remove', headers=AUTH)
        assert r.status_code == 400

    def test_unknown_job_is_404(self, client):
        assert client.post('/app/jobs/nope/cancel', headers=AUTH).status_code == 404

    def test_unknown_action_is_404(self, client):
        job_id = add_video(client).get_json()['job_id']
        assert client.post(f'/app/jobs/{job_id}/explode', headers=AUTH).status_code == 404

    def test_clear_finished(self, client, engine):
        job_id = add_video(client).get_json()['job_id']
        engine.worker.download_complete.emit(job_id, '/x/a.mp4')
        r = client.post('/app/jobs/clear-finished', headers=AUTH)
        assert r.get_json() == {'removed': [job_id]}
        assert client.get('/app/jobs', headers=AUTH).get_json() == []

    def test_report_only_for_failed(self, client):
        job_id = add_video(client).get_json()['job_id']
        assert client.post(f'/app/jobs/{job_id}/report', headers=AUTH).status_code == 400


class TestPicksAndLibrary:
    def open_pick(self, client):
        client.post('/download', json={'type': 'video-list', 'pageUrl': 'https://p', 'pageTitle': 'P',
                                       'videos': [{'url': 'https://cdn/a.mp4'}, {'url': 'https://cdn/b.mp4'}]})
        return client.get('/app/state', headers=AUTH).get_json()['picks'][0]['id']

    def test_resolve_pick(self, client, engine):
        pick_id = self.open_pick(client)
        r = client.post(f'/app/picks/{pick_id}', json={'indices': [1]}, headers=AUTH)
        assert len(r.get_json()['job_ids']) == 1
        assert engine.jobs()[0]['url'] == 'https://cdn/b.mp4'

    def test_resolve_rejects_bad_indices(self, client):
        pick_id = self.open_pick(client)
        r = client.post(f'/app/picks/{pick_id}', json={'indices': ['1']}, headers=AUTH)
        assert r.status_code == 400

    def test_dismiss_pick(self, client):
        pick_id = self.open_pick(client)
        assert client.delete(f'/app/picks/{pick_id}', headers=AUTH).get_json() == {'dismissed': True}

    def test_library_filters_and_removal(self, client, engine):
        a = add_video(client).get_json()['job_id']
        b = add_video(client, 'https://vimeo.com/1').get_json()['job_id']
        engine.worker.download_complete.emit(a, '/x/a.mp4')
        engine.worker.download_complete.emit(b, '/x/b.mp4')
        assert len(client.get('/app/library', headers=AUTH).get_json()) == 2
        vimeo = client.get('/app/library?source=Vimeo', headers=AUTH).get_json()
        assert [e['id'] for e in vimeo] == [b]
        sources = client.get('/app/library/sources', headers=AUTH).get_json()
        assert {s['source'] for s in sources} == {'YouTube', 'Vimeo'}
        assert client.delete(f'/app/library/{a}', headers=AUTH).status_code == 200
        assert client.delete(f'/app/library/{a}', headers=AUTH).status_code == 404


class TestSettings:
    def test_patch_settings(self, client):
        r = client.patch('/app/settings', json={'keep_original': True}, headers=AUTH)
        assert r.status_code == 200 and r.get_json()['keep_original'] is True

    def test_patch_rejects_bad_values(self, client):
        r = client.patch('/app/settings', json={'metadata_option': 'all'}, headers=AUTH)
        assert r.status_code == 400


class TestEvents:
    def read_events(self, response, count):
        events = []
        for chunk in response.response:
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            if text.startswith(':'):
                continue
            lines = dict(line.split(': ', 1) for line in text.strip().splitlines())
            events.append((lines['event'], json.loads(lines['data'])))
            if len(events) == count:
                break
        return events

    def test_stream_starts_with_snapshot_then_follows_the_engine(self, client, engine):
        response = client.get('/app/events', headers=AUTH, buffered=False)
        assert response.mimetype == 'text/event-stream'
        stream = iter(response.response)
        first = next(stream)
        assert first.decode().startswith('event: snapshot')
        job = engine.submit({'type': 'video', 'url': 'https://youtu.be/x', 'title': 'X'})
        engine.worker.progress_update.emit(job['job_id'], 25, 'quarter')
        rest = self.read_events(response, 2)
        assert [e for e, _ in rest] == ['job', 'job']
        assert rest[1][1]['progress'] == 0.25
        response.close()

    def test_stream_needs_token(self, client):
        assert client.get('/app/events').status_code == 401
