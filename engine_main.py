#!/usr/bin/env python3
"""
dlwithit engine, headless: the download engine plus the local API, no window.

The native Mac app starts this in the background and drives it over
http://127.0.0.1:5555/app/ (see api/flask_server.py). The browser extension
keeps talking to the same port exactly as it did to the Qt app.

    python engine_main.py [--port 5555] [--parent-pid PID]

The app's secret token comes from the DLWITHIT_TOKEN environment variable
(a random one is made if it's missing). Port, token and process id are written
to engine.json in the app-support folder, readable only by this user, so an
app that finds the engine already running can attach to it.
"""

import argparse
import json
import os
import secrets
import signal
import socket
import sys
import threading
import time

# When running from a frozen PyInstaller bundle, bundled binaries (ffmpeg,
# ffprobe, deno) sit in sys._MEIPASS; put them on PATH for yt-dlp.
if getattr(sys, 'frozen', False):
    _bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    os.environ['PATH'] = _bundle_dir + os.pathsep + os.environ.get('PATH', '')

from api.flask_server import FlaskServer  # noqa: E402
from core.engine import Engine  # noqa: E402
from core.library import app_support_dir  # noqa: E402

ENGINE_INFO = app_support_dir() / 'engine.json'


def port_is_free(port):
    """True if nothing is listening on 127.0.0.1:port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0


def write_engine_info(port, token):
    """Record how to reach this engine, readable only by the current user."""
    ENGINE_INFO.write_text(json.dumps({'port': port, 'token': token, 'pid': os.getpid()}))
    os.chmod(ENGINE_INFO, 0o600)


def remove_engine_info():
    try:
        info = json.loads(ENGINE_INFO.read_text())
        if info.get('pid') == os.getpid():
            ENGINE_INFO.unlink()
    except Exception:
        pass


def watch_parent(parent_pid, on_gone):
    """Stop the engine if the app that started it goes away without saying so."""
    def loop():
        while True:
            time.sleep(2)
            try:
                os.kill(parent_pid, 0)
            except ProcessLookupError:
                on_gone()
                return
            except PermissionError:
                pass  # exists, owned by someone else — not our parent's fate to judge
    threading.Thread(target=loop, daemon=True).start()


def main(argv=None):
    parser = argparse.ArgumentParser(description='dlwithit download engine (headless)')
    parser.add_argument('--port', type=int, default=5555)
    parser.add_argument('--parent-pid', type=int, default=None,
                        help='quit when this process exits (the app that started the engine)')
    args = parser.parse_args(argv)

    if not port_is_free(args.port):
        print(f"[engine] Port {args.port} is already in use — is dlwithit already running?",
              file=sys.stderr)
        return 2

    token = os.environ.get('DLWITHIT_TOKEN') or secrets.token_urlsafe(32)
    engine = Engine()
    server = FlaskServer(port=args.port, engine=engine, token=token)

    stopping = threading.Event()

    def shutdown(*_):
        if stopping.is_set():
            return
        stopping.set()
        print("[engine] Shutting down")
        engine.stop(timeout_ms=3000)
        remove_engine_info()
        os._exit(0)

    server.on_shutdown = shutdown
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    if args.parent_pid:
        watch_parent(args.parent_pid, shutdown)

    engine.start()
    write_engine_info(args.port, token)
    print(f"[engine] dlwithit engine on http://127.0.0.1:{args.port}", flush=True)
    server.run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
