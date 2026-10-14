"""
The download engine: owns the queue, the workers, and the state of every job.

The native Mac (and later Windows) apps never touch yt-dlp or ffmpeg
themselves. They talk to this engine over the local API (api/flask_server.py)
and redraw from the job snapshots it publishes. Everything that decides *how*
something is downloaded lives here or below; the apps only display it.

Jobs are plain dicts so they serialise straight to JSON:

    id, url, page_url, source, kind ('image' | 'video' | 'direct-video'),
    title, thumbnail, state, progress (0–1 or None), status_text,
    file_path, file_count, error, error_detail, can_convert,
    created_at, finished_at, in_list

state is one of ACTIVE_STATES or FINISHED_STATES. in_list goes False when the
user clears a finished job from the list; the library keeps it for the Gallery.

A "pick" is a page (or playlist) with several videos waiting for the user to
choose which to download. The app shows a picker and answers resolve_pick().
"""

import itertools
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue
from urllib.parse import urlparse

from config.settings import Settings
from .downloader import DownloadWorker
from .encoder import EncodingWorker, file_needs_encoding
from .error_reporter import summarize_error
from .events import Signal
from .library import Library
from .media_list import dedupe_videos, merge_video_lists
from .routing import route_picked_video, source_name
from .url_router import classify_pasted_url

# Progress-only updates are published at most this often per job; state
# changes always go out at once. yt-dlp reports progress many times a second.
PROGRESS_INTERVAL = 0.25

ACTIVE_STATES = frozenset({'queued', 'preparing', 'downloading', 'merging', 'converting'})
FINISHED_STATES = frozenset({'done', 'skipped', 'failed', 'cancelled'})

# Settings the engine owns and the apps may change, with their defaults.
# App-only preferences (menu bar, Dock, login item) live in each app.
DOWNLOAD_SETTINGS = {
    'encode_vp9': True,
    'keep_original': False,
    'organize_by_platform': True,
    'metadata_option': 'none',
    'use_custom_location': False,
    'custom_location': '',
}
METADATA_OPTIONS = ('none', 'embedded', 'sidecar')


def default_save_path():
    return str(Path.home() / 'Downloads' / 'dlwithit')


class EngineError(ValueError):
    """A request the engine refuses, with a message fit to show the user."""


class Engine:
    job_changed = Signal(dict)      # a job snapshot, after any change
    job_removed = Signal(str)       # job id, when it leaves the list
    pick_changed = Signal(dict)     # a pick opened or gained videos
    pick_closed = Signal(str)       # pick id, once answered or dismissed
    settings_changed = Signal(dict)

    def __init__(self, library=None, settings_store=Settings):
        self._lock = threading.RLock()
        self._jobs = {}             # id -> job, in the order they arrived
        self._requests = {}         # id -> (queue item, is_direct), kept for retry
        self._picks = {}
        self._counter = itertools.count(1)
        self._last_publish = {}     # id -> monotonic time of last published snapshot
        self.library = library if library is not None else Library()
        self._settings_store = settings_store

        self.download_queue = Queue()
        self.worker = DownloadWorker(self.download_queue)
        self.encoder = EncodingWorker()
        self._connect_workers()

    # ---- lifecycle ---------------------------------------------------------

    def start(self):
        self.worker.start()
        self.encoder.start()

    def stop(self, timeout_ms=5000):
        self.encoder.stop()
        self.download_queue.put(None)
        self.encoder.wait(timeout_ms)
        self.worker.wait(timeout_ms)

    # ---- reading -----------------------------------------------------------

    def jobs(self):
        """Jobs still in the list, newest first."""
        with self._lock:
            return [dict(j) for j in reversed(self._jobs.values()) if j['in_list']]

    def get_job(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def picks(self):
        with self._lock:
            return [self._pick_snapshot(p) for p in self._picks.values()]

    # ---- requests from the extension or the app ----------------------------

    def submit(self, payload):
        """Accept an extension-style request. Returns {'status', 'job_id' | 'pick_id'}."""
        if not isinstance(payload, dict):
            raise EngineError("Expected a JSON object.")
        if payload.get('type') == 'video-list':
            videos = payload.get('videos') or []
            if not videos:
                raise EngineError("No videos in the list.")
            page_url = payload.get('pageUrl') or ''
            pick = self._open_pick(
                page_url=page_url,
                page_title=payload.get('pageTitle') or page_url,
                source=payload.get('source') or (urlparse(page_url).hostname or ''),
                videos=videos,
                from_playlist=False,
            )
            return {'status': 'pick', 'pick_id': pick['id']}
        if not payload.get('url'):
            raise EngineError("No URL to download.")
        job = self._enqueue(payload, direct=payload.get('type') == 'direct-video')
        return {'status': 'queued', 'job_id': job['id']}

    def submit_link(self, url):
        """A link pasted into the app. Raises EngineError when there's no media to find."""
        url = (url or '').strip()
        kind = classify_pasted_url(url)
        if kind == 'unsupported':
            raise EngineError(
                "We couldn't find any media at this link. Some pages load videos only when "
                "you scroll or interact. Open the page in your browser and use the extension's "
                "Video Download or Pick Images instead.")
        return self.submit({
            'url': url, 'type': kind, 'pageUrl': url,
            'title': (os.path.basename(urlparse(url).path) or url) if kind == 'image' else url,
        })

    def cancel(self, job_id):
        job = self._require(job_id)
        if job['state'] not in ACTIVE_STATES:
            return job
        self.worker.cancel_download(job_id)
        self.encoder.cancel_job(job_id)
        return self._update(job_id, status_text='Cancelling…')

    def retry(self, job_id):
        job = self._require(job_id)
        if job['state'] not in ('failed', 'cancelled'):
            raise EngineError("Only failed or cancelled downloads can be retried.")
        item, _ = self._requests[job_id]
        item = dict(item, **self._download_options())
        self._requests[job_id] = (item, self._requests[job_id][1])
        self._update(job_id, state='queued', progress=None, status_text='Waiting…',
                     error=None, error_detail=None, finished_at=None, in_list=True)
        self.download_queue.put(item)
        return self.get_job(job_id)

    def convert(self, job_id):
        """Convert a finished WebM/VP9/AV1 download to MP4, keeping the original."""
        job = self._require(job_id)
        if job['state'] != 'done' or not job['file_path'] or not os.path.exists(job['file_path']):
            raise EngineError("That file isn't available to convert.")
        self._update(job_id, state='converting', progress=None,
                     status_text='Waiting to convert…', can_convert=False)
        self.encoder.add_job(job_id, job['file_path'], True, {})
        return self.get_job(job_id)

    def remove(self, job_id):
        """Take a finished job out of the list. It stays in the library."""
        job = self._require(job_id)
        if job['state'] in ACTIVE_STATES:
            raise EngineError("Cancel the download before removing it.")
        with self._lock:
            self._jobs[job_id]['in_list'] = False
        self.job_removed.emit(job_id)

    def clear_finished(self):
        """Remove every finished job from the list. Returns the ids removed."""
        with self._lock:
            ids = [j['id'] for j in self._jobs.values()
                   if j['in_list'] and j['state'] in FINISHED_STATES]
            for job_id in ids:
                self._jobs[job_id]['in_list'] = False
        for job_id in ids:
            self.job_removed.emit(job_id)
        return ids

    def resolve_pick(self, pick_id, indices):
        """Download the chosen videos (by index into the pick's list) and close the pick."""
        with self._lock:
            pick = self._picks.pop(pick_id, None)
        if pick is None:
            raise EngineError("That list of videos is no longer open.")
        chosen = [pick['videos'][i] for i in indices if 0 <= i < len(pick['videos'])]
        job_ids = []
        for video in chosen:
            kind, payload = route_picked_video(
                video, pick['page_url'], pick['source'], from_playlist=pick['from_playlist'])
            job_ids.append(self._enqueue(payload, direct=(kind == 'direct'))['id'])
        self.pick_closed.emit(pick_id)
        return job_ids

    def dismiss_pick(self, pick_id):
        with self._lock:
            existed = self._picks.pop(pick_id, None) is not None
        if existed:
            self.pick_closed.emit(pick_id)
        return existed

    # ---- settings ----------------------------------------------------------

    def get_settings(self):
        stored = self._settings_store.load()
        current = {k: stored.get(k, default) for k, default in DOWNLOAD_SETTINGS.items()}
        current['save_path'] = self._save_path(current)
        current['default_save_path'] = default_save_path()
        return current

    def update_settings(self, changes):
        """Apply a partial update. Unknown keys and bad values are refused, nothing saved."""
        if not isinstance(changes, dict):
            raise EngineError("Expected a JSON object.")
        unknown = set(changes) - set(DOWNLOAD_SETTINGS)
        if unknown:
            raise EngineError(f"Unknown setting: {', '.join(sorted(unknown))}")
        for key, value in changes.items():
            if key == 'metadata_option':
                if value not in METADATA_OPTIONS:
                    raise EngineError(f"metadata_option must be one of {', '.join(METADATA_OPTIONS)}")
            elif key == 'custom_location':
                if not isinstance(value, str) or not os.path.isabs(os.path.expanduser(value)):
                    raise EngineError("The save folder must be a full path.")
                folder = Path(os.path.expanduser(value))
                if folder.exists() and not folder.is_dir():
                    raise EngineError("The save location must be a folder.")
                changes[key] = str(folder)
            elif not isinstance(value, bool):
                raise EngineError(f"{key} must be true or false")
        stored = self._settings_store.load()
        stored.update(changes)
        self._settings_store.save(stored)
        current = self.get_settings()
        self.settings_changed.emit(current)
        return current

    # ---- internals: jobs ---------------------------------------------------

    def _new_id(self):
        # Timestamp first so ids sort by arrival, like the Qt app's; the counter
        # keeps two requests in the same microsecond apart.
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{next(self._counter)}"

    def _save_path(self, settings=None):
        settings = settings or self.get_settings()
        if settings.get('use_custom_location') and settings.get('custom_location'):
            return settings['custom_location']
        return default_save_path()

    def _download_options(self):
        s = self.get_settings()
        return {
            'save_path': s['save_path'],
            'encode_vp9': s['encode_vp9'],
            'keep_original': s['keep_original'],
            'organize_by_platform': s['organize_by_platform'],
            'metadata_option': s['metadata_option'],
        }

    def _enqueue(self, data, direct=False):
        job_id = self._new_id()
        url = data['url']
        kind = 'direct-video' if direct else data.get('type', 'video')
        title = data.get('title') or 'Untitled'
        if kind == 'image':
            title = os.path.basename(urlparse(url).path) or 'Image'
        page_url = data.get('pageUrl') or data.get('source') or url
        if kind == 'image' and not data.get('thumbnail'):
            thumbnail = url
        else:
            thumbnail = data.get('thumbnail')

        item = {
            'id': job_id,
            'url': url,
            'type': kind,
            'title': data.get('title', 'video') if direct else data.get('title'),
            'referrer': data.get('pageUrl', data.get('source')),
            'quality': 'best',
            'detectedVideos': data.get('detectedVideos'),
            'skip_playlist_detection': data.get('skip_playlist_detection', False),
            'playlist_index': data.get('playlist_index'),
        }
        item.update(self._download_options())

        job = {
            'id': job_id, 'url': url, 'page_url': page_url,
            'source': source_name(page_url), 'kind': kind,
            'title': title, 'thumbnail': thumbnail,
            'state': 'queued', 'progress': None, 'status_text': 'Waiting…',
            'file_path': None, 'file_count': 1,
            'error': None, 'error_detail': None, 'can_convert': False,
            'created_at': time.time(), 'finished_at': None, 'in_list': True,
        }
        with self._lock:
            self._jobs[job_id] = job
            self._requests[job_id] = (item, direct)
        self.job_changed.emit(dict(job))
        self.download_queue.put(item)
        return dict(job)

    def _require(self, job_id):
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def _update(self, job_id, **fields):
        """Change a job's fields and publish it. Ignores jobs that no longer exist."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            job.update(fields)
            snapshot = dict(job)
            now = time.monotonic()
            if set(fields) <= {'progress', 'status_text'}:
                if now - self._last_publish.get(job_id, 0) < PROGRESS_INTERVAL:
                    return snapshot
            self._last_publish[job_id] = now
        if snapshot['state'] in FINISHED_STATES and 'state' in fields:
            self.library.record(snapshot)
        self.job_changed.emit(snapshot)
        return snapshot

    def _state(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            return job['state'] if job else None

    # ---- internals: picks --------------------------------------------------

    def _open_pick(self, page_url, page_title, source, videos, from_playlist):
        videos = dedupe_videos(videos)
        with self._lock:
            # A second scan of the same page joins the picker that's already open.
            for pick in self._picks.values():
                if pick['page_url'] == page_url and pick['from_playlist'] == from_playlist:
                    pick['videos'], _ = merge_video_lists(pick['videos'], videos)
                    snapshot = self._pick_snapshot(pick)
                    break
            else:
                pick = {
                    'id': f"pick_{self._new_id()}", 'page_url': page_url,
                    'page_title': page_title, 'source': source,
                    'videos': videos, 'from_playlist': from_playlist,
                    'created_at': time.time(),
                }
                self._picks[pick['id']] = pick
                snapshot = self._pick_snapshot(pick)
        self.pick_changed.emit(snapshot)
        return snapshot

    @staticmethod
    def _pick_snapshot(pick):
        return dict(pick, videos=[dict(v) for v in pick['videos']])

    # ---- worker callbacks (these run on worker threads) --------------------

    def _connect_workers(self):
        w, e = self.worker, self.encoder
        w.status_update.connect(self._on_status)
        w.progress_update.connect(self._on_progress)
        w.download_complete.connect(self._on_complete)
        w.download_error.connect(self._on_error)
        w.download_cancelled.connect(self._on_cancelled)
        w.download_skipped.connect(self._on_skipped)
        w.encoding_needed.connect(self._on_encoding_needed)
        w.playlist_detected.connect(self._on_playlist)
        e.encoding_started.connect(self._on_encoding_started)
        e.encoding_progress.connect(self._on_progress)
        e.encoding_complete.connect(self._on_complete)
        e.encoding_error.connect(self._on_encoding_error)
        e.encoding_cancelled.connect(self._on_cancelled)

    def _on_status(self, job_id, status):
        if status.startswith('thumbnail:'):
            self._update(job_id, thumbnail=status[len('thumbnail:'):])
        elif status.startswith('title:'):
            self._update(job_id, title=status[len('title:'):])
        elif status == 'downloading':
            self._update(job_id, state='downloading', status_text='Downloading…')
        elif status == 'merging':
            self._update(job_id, state='merging', progress=1.0, status_text='Merging…')
        elif status == 'encoding':
            self._update(job_id, state='converting', progress=0.0, status_text='Converting to MP4…')
        elif status.startswith('embedding') or status.startswith('adding metadata'):
            self._update(job_id, status_text='Adding metadata…')
        else:
            # "Preparing...", "Reading video 4 of 12...", "Retrying with direct URL..."
            fields = {'status_text': status[:1].upper() + status[1:]}
            if self._state(job_id) == 'queued':
                fields['state'] = 'preparing'
            self._update(job_id, **fields)

    def _on_progress(self, job_id, percent, text):
        fields = {'progress': max(0.0, min(1.0, percent / 100.0)), 'status_text': text}
        if self._state(job_id) in ('queued', 'preparing'):
            fields['state'] = 'downloading'
        self._update(job_id, **fields)

    def _on_complete(self, job_id, path):
        file_path, _, count = path.partition('|MULTI|')
        file_count = int(count.split()[0]) if count else 1
        can_convert = False
        if file_count == 1:
            try:
                can_convert = file_needs_encoding(file_path)
            except Exception:
                can_convert = False
        self._update(job_id, state='done', progress=1.0,
                     status_text=f'{file_count} files' if file_count > 1 else 'Complete',
                     file_path=file_path, file_count=file_count,
                     can_convert=can_convert, finished_at=time.time())

    def _on_error(self, job_id, error):
        self._update(job_id, state='failed', progress=None,
                     status_text='Failed', error=summarize_error(error),
                     error_detail=error, finished_at=time.time())

    def _on_encoding_error(self, job_id, error):
        self._update(job_id, state='failed', progress=None, status_text='Conversion failed',
                     error=f"Conversion: {summarize_error(error)}",
                     error_detail=f"Conversion Error: {error}", finished_at=time.time())

    def _on_cancelled(self, job_id):
        self._update(job_id, state='cancelled', progress=None,
                     status_text='Cancelled', finished_at=time.time())

    def _on_skipped(self, job_id, reason, path):
        self._update(job_id, state='skipped', progress=1.0, status_text=reason,
                     file_path=path, finished_at=time.time())

    def _on_encoding_needed(self, job_id, path, keep_original, metadata_info):
        self._update(job_id, state='converting', progress=None,
                     status_text='Waiting to convert…', file_path=path)
        self.encoder.add_job(job_id, path, keep_original, metadata_info)

    def _on_encoding_started(self, job_id):
        self._update(job_id, state='converting', progress=0.0, status_text='Converting to MP4…')

    def _on_playlist(self, job_id, data):
        # The page held several videos: swap the placeholder job for a picker.
        with self._lock:
            job = self._jobs.pop(job_id, None)
            self._requests.pop(job_id, None)
        if job is not None:
            self.job_removed.emit(job_id)
        self._open_pick(
            page_url=data.get('pageUrl', ''),
            page_title=data.get('pageTitle') or data.get('pageUrl', ''),
            source=data.get('source', ''),
            videos=data.get('videos', []),
            from_playlist=True,
        )
