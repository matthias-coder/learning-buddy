"""Importiert alle JSONs aus examples/ai-generated/ und prüft, dass keine Fehler auftreten."""
from pathlib import Path

import pytest

from school_test_engine.importer.json_import import ImportError, import_from_file
from school_test_engine.storage import connect, run_migrations, tests_repo

AI_DIR = Path(__file__).parent.parent / "examples" / "ai-generated"


def _all_json_files() -> list[Path]:
    return sorted(AI_DIR.glob("*.json"))


@pytest.fixture
def conn(tmp_path):
    db = tmp_path / "test.sqlite3"
    c = connect(db)
    run_migrations(c)
    yield c
    c.close()


def test_ai_generated_dir_exists() -> None:
    assert AI_DIR.exists(), f"Verzeichnis fehlt: {AI_DIR}"
    files = _all_json_files()
    assert len(files) == 10, f"Erwartet 10 JSONs, gefunden: {len(files)}"


@pytest.mark.parametrize("json_path", _all_json_files(), ids=lambda p: p.name)
def test_ai_generated_json_imports(conn, json_path: Path) -> None:
    try:
        test_id = import_from_file(conn, json_path, user_id=1)
    except ImportError as e:
        pytest.fail(f"Import von {json_path.name} fehlgeschlagen:\n{e}")
    assert test_id > 0

    row = conn.execute(
        "SELECT title, subject FROM tests WHERE id = ?", (test_id,)
    ).fetchone()
    assert row is not None
    assert row["title"]
    assert row["subject"] in {"Mathe", "Englisch", "Bio", "Physik", "Chemie", "Geschichte"}

    qcount = conn.execute(
        "SELECT COUNT(*) AS n FROM questions WHERE test_id = ?", (test_id,)
    ).fetchone()["n"]
    assert qcount >= 1


def test_all_subjects_covered(conn) -> None:
    """Sicherstellen, dass die 10 Tests alle 6 Fächer abdecken."""
    for path in _all_json_files():
        import_from_file(conn, path, user_id=1)

    subjects = {
        r["subject"]
        for r in conn.execute("SELECT DISTINCT subject FROM tests").fetchall()
    }
    expected = {"Mathe", "Englisch", "Bio", "Physik", "Chemie", "Geschichte"}
    assert expected.issubset(subjects), f"Fehlende Fächer: {expected - subjects}"

    all_tests = tests_repo.list_tests(conn, user_id=1)
    assert len(all_tests) == 10
