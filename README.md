# Learning Buddy

Übungs-Test-Engine für die Realschule (8. Klasse) — KI-generierte Fragen importieren,
üben, Wissenslücken finden.

## Download

**Windows:** [LearningBuddy-Setup.exe herunterladen](https://github.com/matthias-coder/learning-buddy/releases/latest/download/LearningBuddy-Setup.exe) · Startseite: <https://matthias-coder.github.io/learning-buddy/>

Der Installer ist nicht signiert. Bei der Windows-Warnung „Weitere Informationen“ → „Trotzdem ausführen“ wählen.

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

Releases baut GitHub Actions automatisch: Tag `vX.Y.Z` pushen → [`.github/workflows/release.yml`](.github/workflows/release.yml) testet, baut den Installer und veröffentlicht ihn als GitHub Release.
Lokaler Build: siehe [`packaging/README.md`](packaging/README.md).
