from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME")
    if base:
        root = Path(base)
    else:
        root = Path.home() / ".local" / "share"
    path = root / "school-test-engine"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    override = os.environ.get("SCHOOL_TEST_ENGINE_DB")
    if override:
        return Path(override)
    return data_dir() / "db.sqlite3"
