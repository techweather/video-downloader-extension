# dlwithit engine API

The download engine (`core/engine.py`) runs headless (`engine_main.py`) and serves this API on `http://127.0.0.1:5555`. The native Mac app uses it today; the Windows app will use the same contract. Source of truth: `api/flask_server.py`.

## Two audiences

| Paths | Who calls them | Auth | CORS |
|---|---|---|---|
| `/download`, `/classify`, `/health`, `/` | Browser extension | none | open (echoes the caller's origin) |
| `/app/…` | Native app | `X-Dlwithit-Token` header | none — web pages can't reach them |

The token comes from `DLWITHIT_TOKEN` when the app launches the engine, or is generated. `engine_main.py` writes `{port, token, pid}` to `~/Library/Application Support/dlwithit/engine.json` (mode 0600) so an app can attach to an engine that's already running.

When the Qt window runs instead (`native_app.py`), there is no engine: `/app/…` answers 503 and `/health` reports `"engine": false`.

## Objects

**Job** — one download in the list.

```json
{
  "id": "20261014_130846_290652_2",
  "url": "https://www.youtube.com/watch?v=…",
  "page_url": "https://www.youtube.com/watch?v=…",
  "source": "YouTube",
  "kind": "video",                // image | video | direct-video
  "title": "Me at the zoo",
  "thumbnail": "https://i.ytimg.com/…",
  "state": "downloading",         // queued preparing downloading merging converting | done skipped failed cancelled
  "progress": 0.42,               // 0–1, or null when unknown
  "status_text": "12.3MiB of 29.6MiB at 1.8MiB/s",
  "file_path": null,
  "file_count": 1,
  "error": null,                  // one line, for the row
  "error_detail": null,           // full text, for Error Details / reports
  "can_convert": false,           // finished file is still WebM/VP9/AV1
  "created_at": 1792008526.29,
  "finished_at": null,
  "in_list": true                 // false once cleared; the library keeps it
}
```

**Pick** — a page or playlist with several videos, waiting for the user to choose.

```json
{ "id": "pick_…", "page_url": "…", "page_title": "…", "source": "…",
  "videos": [{ "url": "…", "title": "…", "thumbnail": "…", "duration": 61.0, "uploader": "…" }],
  "from_playlist": false }
```

**Library entry** — a finished, skipped or failed download, kept after clearing. Same fields as a job minus the live ones, plus `exists` (is the file still on disk).

**Settings** — `encode_vp9`, `keep_original`, `organize_by_platform`, `metadata_option` (`none` | `embedded` | `sidecar`), `use_custom_location`, `custom_location`, and read-only `save_path`, `default_save_path`. Stored in `~/.dlwithit_settings.json`, shared with the Qt app.

## Endpoints (all need the token)

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/app/state` | | `{jobs, picks, settings, version, ytdlp_version}` |
| GET | `/app/events` | | Server-Sent Events, see below |
| GET | `/app/jobs` | | jobs in the list, newest first |
| POST | `/app/jobs` | `{url}` | `{status: "queued", job_id}` · 400 with a user-facing `error` when there's no media |
| POST | `/app/jobs/<id>/cancel` | | job |
| POST | `/app/jobs/<id>/retry` | | job (failed or cancelled only) |
| POST | `/app/jobs/<id>/convert` | | job (done, file present; keeps the original) |
| POST | `/app/jobs/<id>/remove` | | `{ok}` (finished only) |
| POST | `/app/jobs/<id>/report` | | `{ok}` — sends the anonymous error report (failed only) |
| POST | `/app/jobs/clear-finished` | | `{removed: [ids]}` |
| POST | `/app/picks/<id>` | `{indices: [0, 2]}` | `{job_ids}` |
| DELETE | `/app/picks/<id>` | | `{dismissed}` |
| GET | `/app/library?source=&state=&limit=` | | entries, newest first |
| GET | `/app/library/sources` | | `[{source, count}]` |
| DELETE | `/app/library/<id>` | | `{ok}` — forgets the entry, never the file |
| GET | `/app/settings` | | settings |
| PATCH | `/app/settings` | any subset of the writable settings | settings · 400 on unknown keys or bad values (nothing saved) |
| GET | `/app/updates` | | `{app_version, latest_app_version, app_update_available, release_url, ytdlp_version, latest_ytdlp_version}` |
| POST | `/app/shutdown` | | `{ok}`, then the engine exits |

Errors are `{"error": "message"}` with 400 (refused), 401 (token), 404 (unknown id/action) or 503 (no engine).

## Live events (`/app/events`)

```
event: snapshot      data: {jobs, picks, settings, version, ytdlp_version}   ← always first
event: job           data: <job>                                            ← any change
event: job_removed   data: {"id": "…"}
event: pick          data: <pick>                                           ← opened or grew
event: pick_closed   data: {"id": "…"}
event: settings      data: <settings>
: keepalive                                                                 ← every 15 s when idle
```

Each event has exactly one `data:` line. Progress-only job updates arrive at most 4 times a second per job; state changes are immediate. After a reconnect, the new snapshot replaces everything — no replay needed.
