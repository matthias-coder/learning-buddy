from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from ..models.test import Test
from ..storage import tests_repo


class ImportError(Exception):
    """Raised when a test JSON cannot be imported. Message is human-readable (German)."""


def import_from_file(conn: sqlite3.Connection, path: Path, user_id: int) -> int:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ImportError(f"Datei konnte nicht gelesen werden: {e}") from e
    return import_from_string(conn, source, user_id)


def import_from_string(conn: sqlite3.Connection, source: str, user_id: int) -> int:
    try:
        raw = json.loads(source)
    except json.JSONDecodeError as e:
        raise ImportError(f"Ungültiges JSON: {e.msg} (Zeile {e.lineno}, Spalte {e.colno})") from e

    try:
        test = Test.model_validate(raw)
    except ValidationError as e:
        raise ImportError(_format_validation_error(e)) from e

    return tests_repo.insert_test(conn, test, source, user_id)


def _format_validation_error(err: ValidationError) -> str:
    lines = ["Validierungsfehler im Test-JSON:"]
    for e in err.errors():
        loc = ".".join(str(p) for p in e["loc"])
        lines.append(f"  - {loc}: {e['msg']}")
    return "\n".join(lines)
