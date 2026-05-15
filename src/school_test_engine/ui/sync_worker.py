"""QThread-friendly wrapper around ical_sync.service.sync_feed.

The worker opens its own SQLite connection inside `run()` because the
default-mode SQLite connection is not thread-safe to share. The result
is emitted via the `finished` signal on the originating thread.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..ical_sync import sync_feed


class SyncWorker(QObject):
    finished = Signal(object)  # emits a SyncResult

    def __init__(self, db_path: Path | str, user_id: int):
        super().__init__()
        self.db_path = Path(db_path)
        self.user_id = user_id

    def run(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            result = sync_feed(conn, self.user_id)
        finally:
            conn.close()
        self.finished.emit(result)
