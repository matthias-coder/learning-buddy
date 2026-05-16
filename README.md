# Learning Buddy

Übungs-Test-Engine für die Realschule (8. Klasse) — KI-generierte Fragen importieren,
üben, Wissenslücken finden.

## Stack

Python 3.12, PySide6, SQLite, pytest.

## Entwicklung

```bash
python -m venv .venv
source .venv/bin/activate              # Linux/macOS
# oder: .venv\Scripts\activate         # Windows
pip install -e .[dev]
pytest -q                              # Test-Suite läuft
python -m school_test_engine           # App starten
```

## Windows-Distribution

Build-Anleitung für die `.exe`-Installer-Erzeugung: siehe [`packaging/README.md`](packaging/README.md).
