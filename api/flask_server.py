"""
Flask API server for dlwithit.

Two audiences share this server on 127.0.0.1:5555:

* The browser extension — /download, /classify, /health and /. These stay
  exactly as the extension expects, with CORS open so it can call them.

* The native app — everything under /app/. These drive the download engine
  (core/engine.py): list and control jobs, answer pickers, read the library,
  change settings, and stream live updates. They need the engine's token in
  an X-Dlwithit-Token header and have no CORS, so a web page can't reach them.

When the Qt window runs the show (native_app.py) there is no engine and the
/app/ endpoints answer 503; /download hands requests to the window instead.
"""

import hmac
import json
import os
import queue
import threading

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

from version import __version__

TOKEN_HEADER = 'X-Dlwithit-Token'

# Paths the extension calls. Matched with re.match, so each is anchored.
EXTENSION_PATHS = (r'/download$', r'/classify$', r'/health$', r'/$')


class EventHub:
    """Fans engine events out to every connected /app/events stream."""

    def __init__(self):
        self._clients = []
        self._lock = threading.Lock()

    def subscribe(self):
        q = queue.Queue(maxsize=1000)
        with self._lock:
            self._clients.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)

    def publish(self, event, data):
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait((event, data))
            except queue.Full:
                # A client that stopped reading; it will resync from a new snapshot.
                pass

    def client_count(self):
        with self._lock:
            return len(self._clients)


def sse_message(event, data):
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class FlaskServer:
    """
    Flask API server for the browser extension and the native app.
    """

    def __init__(self, port=5555, debug=False, engine=None, token=None,
                 keepalive_seconds=15):
        """
        Args:
            port: Port number to run server on (default: 5555)
            debug: Enable Flask debug mode (default: False)
            engine: core.engine.Engine to drive, or None when the Qt window runs things
            token: secret the native app must send with /app/ requests
            keepalive_seconds: how often an idle event stream sends a heartbeat
        """
        self.port = port
        self.debug = debug
        self.app = Flask(__name__)

        # CORS only for the extension's endpoints.
        CORS(self.app, resources={path: {'origins': '*'} for path in EXTENSION_PATHS})

        # Reference to main application window for signal emission (Qt mode)
        self.window = None
        self.engine = None
        self.token = token
        self.keepalive_seconds = keepalive_seconds
        self.events = EventHub()
        self.on_shutdown = None   # set by engine_main.py

        self._setup_routes()
        self._setup_app_routes()
        if engine is not None:
            self.set_engine(engine)

    def set_window(self, window):
        """Set reference to main application window (Qt mode)."""
        self.window = window

    def set_engine(self, engine):
        """Drive this engine, and forward its events to /app/events streams."""
        self.engine = engine
        engine.job_changed.connect(lambda job: self.events.publish('job', job))
        engine.job_removed.connect(lambda job_id: self.events.publish('job_removed', {'id': job_id}))
        engine.pick_changed.connect(lambda pick: self.events.publish('pick', pick))
        engine.pick_closed.connect(lambda pick_id: self.events.publish('pick_closed', {'id': pick_id}))
        engine.settings_changed.connect(lambda s: self.events.publish('settings', s))

    # ---- extension endpoints ----------------------------------------------

    def _setup_routes(self):
        """Set up the routes the browser extension uses."""

        @self.app.route('/download', methods=['POST'])
        def download():
            """
            Handle download requests from browser extension.

            Expected JSON payload:
            - type: 'image', 'video', 'video-list'
            - url: Media URL (for single downloads)
            - videos: List of video objects (for video-list type)
            - pageUrl: Source page URL
            - title: Media title
            - thumbnail: Thumbnail URL (optional)
            """
            data = request.json

            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            if self.engine is not None:
                from core.engine import EngineError
                try:
                    result = self.engine.submit(data)
                except EngineError as e:
                    return jsonify({"status": "error", "message": str(e)}), 400
                # The extension only looks at "status"; "queued" covers picks too.
                return jsonify(dict(result, status="queued"))

            if not self.window:
                print("[ERROR] Window reference is None!")
                return jsonify({"status": "error", "message": "Application not ready"}), 503

            if data.get('type') == 'video-list':
                # Show the video selector dialog
                self.window.video_list_received.emit(data)
            else:
                # Single download (image, video, etc.)
                self.window.new_download.emit(data)

            return jsonify({"status": "queued"})

        @self.app.route('/classify', methods=['POST'])
        def classify_url():
            data = request.json
            url = data.get('url', '') if data else ''
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    supported = any(
                        ie.suitable(url)
                        for ie in ydl._ies.values()
                        if ie.ie_key() != 'Generic'
                    )
                return jsonify({'supported': supported})
            except Exception:
                return jsonify({'supported': False})

        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check. `engine` tells the native app it can drive this server."""
            return jsonify({
                "status": "healthy",
                "message": "dlwithit API is running",
                "window_connected": self.window is not None,
                "engine": self.engine is not None,
                "version": __version__,
            })

        @self.app.route('/', methods=['GET'])
        def root():
            """Root endpoint with basic information."""
            return jsonify({
                "name": "dlwithit API",
                "version": "1.0.0",
                "endpoints": [
                    {"path": "/download", "method": "POST", "description": "Submit download requests"},
                    {"path": "/health", "method": "GET", "description": "Health check"},
                    {"path": "/", "method": "GET", "description": "API information"}
                ]
            })

    # ---- native app endpoints ---------------------------------------------

    def _setup_app_routes(self):
        app = self.app

        @app.before_request
        def guard_app_routes():
            if not request.path.startswith('/app/'):
                return None
            if self.engine is None:
                return jsonify({"error": "No engine running"}), 503
            sent = request.headers.get(TOKEN_HEADER, '')
            if not self.token or not hmac.compare_digest(sent, self.token):
                return jsonify({"error": "Missing or wrong token"}), 401
            return None

        def engine_call(fn, *args):
            """Run an engine action, turning its refusals into HTTP errors."""
            from core.engine import EngineError
            try:
                return fn(*args)
            except EngineError as e:
                return _error(str(e), 400)
            except KeyError:
                return _error("No such download", 404)

        def _error(message, status):
            response = jsonify({"error": message})
            response.status_code = status
            return response

        def body():
            return request.get_json(silent=True) or {}

        @app.route('/app/state', methods=['GET'])
        def app_state():
            return jsonify(self._snapshot())

        @app.route('/app/events', methods=['GET'])
        def app_events():
            client = self.events.subscribe()
            snapshot = self._snapshot()

            def stream():
                try:
                    yield sse_message('snapshot', snapshot)
                    while True:
                        try:
                            event, data = client.get(timeout=self.keepalive_seconds)
                        except queue.Empty:
                            yield ": keepalive\n\n"
                            continue
                        yield sse_message(event, data)
                finally:
                    self.events.unsubscribe(client)

            return Response(stream_with_context(stream()), mimetype='text/event-stream',
                            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

        @app.route('/app/jobs', methods=['GET'])
        def app_jobs():
            return jsonify(self.engine.jobs())

        @app.route('/app/jobs', methods=['POST'])
        def app_add_link():
            result = engine_call(self.engine.submit_link, body().get('url', ''))
            return result if isinstance(result, Response) else jsonify(result)

        @app.route('/app/jobs/clear-finished', methods=['POST'])
        def app_clear_finished():
            return jsonify({"removed": self.engine.clear_finished()})

        @app.route('/app/jobs/<job_id>/<action>', methods=['POST'])
        def app_job_action(job_id, action):
            actions = {
                'cancel': self.engine.cancel,
                'retry': self.engine.retry,
                'convert': self.engine.convert,
                'remove': self.engine.remove,
                'report': self._report,
            }
            if action not in actions:
                return _error("Unknown action", 404)
            result = engine_call(actions[action], job_id)
            if isinstance(result, Response):
                return result
            return jsonify(result if result is not None else {"ok": True})

        @app.route('/app/picks/<pick_id>', methods=['POST'])
        def app_resolve_pick(pick_id):
            indices = body().get('indices', [])
            if not isinstance(indices, list) or not all(isinstance(i, int) for i in indices):
                return _error("indices must be a list of numbers", 400)
            result = engine_call(self.engine.resolve_pick, pick_id, indices)
            return result if isinstance(result, Response) else jsonify({"job_ids": result})

        @app.route('/app/picks/<pick_id>', methods=['DELETE'])
        def app_dismiss_pick(pick_id):
            return jsonify({"dismissed": self.engine.dismiss_pick(pick_id)})

        @app.route('/app/library', methods=['GET'])
        def app_library():
            limit = request.args.get('limit', 500, type=int)
            return jsonify(self.engine.library.entries(
                source=request.args.get('source') or None,
                state=request.args.get('state') or None,
                limit=max(1, min(limit, 5000))))

        @app.route('/app/library/sources', methods=['GET'])
        def app_library_sources():
            return jsonify(self.engine.library.sources())

        @app.route('/app/library/remove-missing', methods=['POST'])
        def app_library_remove_missing():
            return jsonify({"removed": self.engine.library.remove_missing()})

        @app.route('/app/library/<entry_id>', methods=['PATCH'])
        def app_library_update(entry_id):
            # The app found the file somewhere new (it followed a move, or the user located it).
            path = body().get('file_path')
            if not isinstance(path, str) or not os.path.isabs(path) or not os.path.isfile(path):
                return _error("file_path must be an existing file", 400)
            if not self.engine.library.update_path(entry_id, path):
                return _error("Not in the library", 404)
            return jsonify(self.engine.library.get(entry_id))

        @app.route('/app/library/<entry_id>', methods=['DELETE'])
        def app_library_remove(entry_id):
            if not self.engine.library.remove(entry_id):
                return _error("Not in the library", 404)
            return jsonify({"ok": True})

        @app.route('/app/settings', methods=['GET'])
        def app_get_settings():
            return jsonify(self.engine.get_settings())

        @app.route('/app/settings', methods=['PATCH'])
        def app_update_settings():
            result = engine_call(self.engine.update_settings, body())
            return result if isinstance(result, Response) else jsonify(result)

        @app.route('/app/updates', methods=['GET'])
        def app_updates():
            return jsonify(self._check_updates())

        @app.route('/app/shutdown', methods=['POST'])
        def app_shutdown():
            if self.on_shutdown:
                # Answer first, then stop, so the app gets its reply.
                threading.Timer(0.2, self.on_shutdown).start()
            return jsonify({"ok": True})

    # ---- helpers -----------------------------------------------------------

    def _snapshot(self):
        from core.updater import get_ytdlp_version
        return {
            "jobs": self.engine.jobs(),
            "picks": self.engine.picks(),
            "settings": self.engine.get_settings(),
            "version": __version__,
            "ytdlp_version": get_ytdlp_version(),
        }

    def _report(self, job_id):
        """Send the anonymous error report for a failed job (user-initiated)."""
        from core.engine import EngineError
        from core.error_reporter import send_error_report
        job = self.engine.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        if job['state'] != 'failed':
            raise EngineError("Only failed downloads can be reported.")
        sent = send_error_report(
            error_type='Download Error',
            error_message=job.get('error_detail') or job.get('error') or '',
            url=job.get('url') or '')
        if not sent:
            raise EngineError("The report couldn't be sent. Try again later.")
        return {"ok": True}

    @staticmethod
    def _check_updates():
        """Latest dlwithit and yt-dlp releases from GitHub. Empty strings when offline."""
        from core.app_updater import AppVersionCheckWorker, is_newer
        from core.updater import VersionCheckWorker, get_ytdlp_version
        results = {}
        app_check, ytdlp_check = AppVersionCheckWorker(), VersionCheckWorker()
        app_check.finished.connect(lambda latest, url: results.update(app=(latest, url)))
        ytdlp_check.finished.connect(lambda latest: results.update(ytdlp=latest))
        app_check.start()
        ytdlp_check.start()
        app_check.wait(20000)
        ytdlp_check.wait(20000)
        latest_app, release_url = results.get('app', ('', ''))
        return {
            "app_version": __version__,
            "latest_app_version": latest_app,
            "app_update_available": bool(latest_app) and is_newer(latest_app, __version__),
            "release_url": release_url,
            "ytdlp_version": get_ytdlp_version(),
            "latest_ytdlp_version": results.get('ytdlp', ''),
        }

    def run(self):
        """
        Start the Flask server.

        This method blocks and should typically be run in a separate thread.
        """
        print(f"[INFO] Starting Flask server on port {self.port}")
        self.app.run(
            host='127.0.0.1',
            port=self.port,
            debug=self.debug,
            use_reloader=False,  # Disable reloader to prevent issues with threading
            threaded=True  # Enable threading for concurrent requests
        )

    def shutdown(self):
        """
        Shutdown the Flask server gracefully.

        Note: This requires the server to be running with threaded=True
        """
        try:
            # Get the shutdown function from Werkzeug
            shutdown = request.environ.get('werkzeug.server.shutdown')
            if shutdown:
                shutdown()
                print("[INFO] Flask server shutdown requested")
            else:
                print("[WARNING] Unable to shutdown Flask server gracefully")
        except Exception as e:
            print(f"[ERROR] Error during Flask server shutdown: {e}")


# Convenience function for creating and configuring server
def create_flask_server(port=5555, debug=False):
    """
    Create and configure a Flask server instance.

    Args:
        port: Port number to run server on (default: 5555)
        debug: Enable Flask debug mode (default: False)

    Returns:
        FlaskServer: Configured Flask server instance
    """
    return FlaskServer(port=port, debug=debug)


# Convenience function for running server in background thread
def run_flask_server(server, daemon=True):
    """
    Run Flask server in a background thread.

    Args:
        server: FlaskServer instance to run
        daemon: Whether thread should be daemon thread (default: True)

    Returns:
        Thread: The thread running the Flask server
    """
    from threading import Thread

    flask_thread = Thread(target=server.run, daemon=daemon)
    flask_thread.start()
    return flask_thread
