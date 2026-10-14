"""
The download library: a small SQLite record of every finished download.

The queue forgets a download once it is cleared; the library keeps it so the
native app's Gallery can show past downloads, filtered by site or state.
Removing an entry from the library never touches the file on disk.
"""

import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

COLUMNS = ('id', 'url', 'page_url', 'source', 'kind', 'title', 'thumbnail',
           'file_path', 'file_count', 'state', 'error', 'created_at', 'finished_at')

# Only finished outcomes belong in the library; in-flight jobs live in the engine.
LIBRARY_STATES = frozenset({'done', 'skipped', 'failed'})


def app_support_dir():
    """Per-user folder for dlwithit's own data (library, engine info)."""
    if sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    elif sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    path = base / 'dlwithit'
    path.mkdir(parents=True, exist_ok=True)
    return path


class Library:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or app_support_dir() / 'library.sqlite3')
        self._lock = threading.Lock()
        # One connection shared across the engine's threads, guarded by the lock.
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id TEXT PRIMARY KEY,
                    url TEXT, page_url TEXT, source TEXT, kind TEXT,
                    title TEXT, thumbnail TEXT,
                    file_path TEXT, file_count INTEGER DEFAULT 1,
                    state TEXT, error TEXT,
                    created_at REAL, finished_at REAL
                )""")
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS downloads_finished ON downloads(finished_at DESC)")

    def record(self, job):
        """Insert or update a finished job (a dict with the engine's job fields)."""
        if job.get('state') not in LIBRARY_STATES:
            return
        row = {c: job.get(c) for c in COLUMNS}
        row['finished_at'] = row['finished_at'] or time.time()
        placeholders = ', '.join(':' + c for c in COLUMNS)
        with self._lock, self._db:
            self._db.execute(
                f"INSERT OR REPLACE INTO downloads ({', '.join(COLUMNS)}) VALUES ({placeholders})", row)

    def entries(self, source=None, state=None, limit=500):
        """Newest first. Each entry gains `exists`: whether its file is still on disk."""
        sql = "SELECT * FROM downloads"
        where, args = [], []
        if source:
            where.append("source = ?")
            args.append(source)
        if state:
            where.append("state = ?")
            args.append(state)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY finished_at DESC LIMIT ?"
        args.append(int(limit))
        with self._lock:
            rows = [dict(r) for r in self._db.execute(sql, args)]
        for r in rows:
            r['exists'] = bool(r['file_path']) and os.path.exists(r['file_path'])
        return rows

    def get(self, entry_id):
        with self._lock:
            row = self._db.execute("SELECT * FROM downloads WHERE id = ?", (entry_id,)).fetchone()
        return dict(row) if row else None

    def remove(self, entry_id):
        """Forget one entry. Returns True if it existed. The file itself is left alone."""
        with self._lock, self._db:
            cur = self._db.execute("DELETE FROM downloads WHERE id = ?", (entry_id,))
        return cur.rowcount > 0

    def sources(self):
        """Every source name in the library, with how many downloads came from it."""
        with self._lock:
            rows = self._db.execute(
                "SELECT source, COUNT(*) AS count FROM downloads GROUP BY source ORDER BY count DESC")
            return [dict(r) for r in rows]

    def close(self):
        with self._lock:
            self._db.close()
