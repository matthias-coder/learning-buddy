from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import db_path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or db_path()
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
    )
    cur = conn.execute("SELECT MAX(version) AS v FROM schema_version")
    current = cur.fetchone()["v"] or 0

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    for f in files:
        version = int(f.stem.split("_", 1)[0])
        if version <= current:
            continue
        sql = f.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (version,)
        )
        conn.commit()
