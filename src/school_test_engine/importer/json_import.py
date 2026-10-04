from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from ..models.test import Test
from ..storage import tests_repo


class ImportError(Exception):
    """Raised when a test JSON cannot be imported. Message is human-readable (German)."""


NOT_A_TEST_MESSAGE = (
    "Das sieht nicht nach einem Test aus. Kopiere bitte nur den Teil der "
    "KI-Antwort, der mit { beginnt und mit } endet."
)
UNREADABLE_FILE_MESSAGE = "Die Datei konnte nicht gelesen werden – ist es eine Textdatei?"

_FENCE_RE = re.compile(r"```[a-zA-Z0-9_-]*[ \t]*\r?\n?(.*?)```", re.DOTALL)


def import_from_file(conn: sqlite3.Connection, path: Path, user_id: int) -> int:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ImportError(UNREADABLE_FILE_MESSAGE) from e
    except OSError as e:
        raise ImportError(UNREADABLE_FILE_MESSAGE) from e
    return import_from_string(conn, source, user_id)


def _fingerprint(test: Test) -> str:
    """Normalized content of a test (whitespace/key order independent)."""
    return json.dumps(test.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)


def find_duplicate(conn: sqlite3.Connection, source: str, user_id: int) -> int | None:
    """Id of an already imported, identical test of this user, else None.

    Never raises: unparsable/invalid input yields None so that the regular
    import reports the proper error.
    """
    try:
        raw, _ = _parse_json(source)
        wanted = _fingerprint(Test.model_validate(raw))
    except (ImportError, ValidationError):
        return None
    rows = conn.execute(
        "SELECT id, source_json FROM tests WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    for row in rows:
        try:
            existing = Test.model_validate(json.loads(row["source_json"]))
        except (ValueError, ValidationError, TypeError):
            continue
        if _fingerprint(existing) == wanted:
            return int(row["id"])
    return None


def find_duplicate_in_file(conn: sqlite3.Connection, path: Path, user_id: int) -> int | None:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return find_duplicate(conn, source, user_id)


def _candidates(source: str) -> list[str]:
    """Possible JSON texts inside a pasted AI answer, most specific first."""
    text = source.strip().lstrip("﻿")
    out = [text]
    for m in _FENCE_RE.finditer(text):
        out.append(m.group(1).strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        out.append(text[start : end + 1])
    return out


def _parse_json(source: str) -> tuple[dict, str]:
    first_error: json.JSONDecodeError | None = None
    saw_object_like = False
    for cand in _candidates(source):
        try:
            raw = json.loads(cand)
        except json.JSONDecodeError as e:
            if cand.lstrip().startswith("{"):
                saw_object_like = True
                first_error = first_error or e
            continue
        if isinstance(raw, dict):
            return raw, cand
    if saw_object_like and first_error is not None:
        raise ImportError(
            "Der Test ist nicht vollständig oder hat einen Tippfehler "
            f"(etwa bei Zeile {first_error.lineno}). Kopiere die KI-Antwort bitte "
            "noch einmal komplett, vom ersten { bis zum letzten }."
        ) from first_error
    raise ImportError(NOT_A_TEST_MESSAGE)


def import_from_string(conn: sqlite3.Connection, source: str, user_id: int) -> int:
    raw, json_text = _parse_json(source)

    try:
        test = Test.model_validate(raw)
    except ValidationError as e:
        raise ImportError(_format_validation_error(e)) from e

    return tests_repo.insert_test(conn, test, json_text, user_id)


def _describe_location(loc: tuple) -> tuple[str, str | None]:
    """Return (where, field) in German, e.g. ("Frage 3", "antwort")."""
    where = "Im Test"
    field: str | None = None
    parts = list(loc)
    if len(parts) >= 2 and parts[0] == "questions" and isinstance(parts[1], int):
        where = f"Frage {parts[1] + 1}"
        parts = parts[2:]
    else:
        parts = parts[:]
    names = [str(p) for p in parts if not isinstance(p, int)]
    # discriminated-union tag (e.g. "single_choice") is not a field
    names = [n for n in names if n not in {"single_choice", "multi_choice", "short_answer"}]
    if names:
        field = names[-1]
    return where, field


def _format_validation_error(err: ValidationError) -> str:
    lines = ["Im Test stimmt etwas nicht:"]
    seen: set[str] = set()
    for e in err.errors():
        where, field = _describe_location(tuple(e["loc"]))
        kind = e["type"]
        quoted = f"„{field}“" if field else ""
        if kind == "missing":
            text = f"Feld {quoted} fehlt"
        elif kind == "extra_forbidden":
            text = f"Feld {quoted} gibt es nicht (Tippfehler?)"
        elif kind == "value_error":
            msg = str(e["msg"])
            text = msg.removeprefix("Value error, ")
        elif kind in {"literal_error", "enum"}:
            text = f"Feld {quoted} hat einen nicht erlaubten Wert"
        elif kind.endswith("_type") or kind.endswith("_parsing"):
            text = f"Feld {quoted} hat die falsche Art von Wert"
        elif kind == "too_short" and field:
            text = f"Feld {quoted} ist zu kurz oder leer"
        elif field:
            text = f"Feld {quoted} hat einen ungültigen Wert"
        else:
            text = "Ein Wert ist ungültig"
        line = f"  - {where}: {text}"
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return "\n".join(lines)
