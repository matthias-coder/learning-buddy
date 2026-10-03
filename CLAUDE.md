# CLAUDE.md – Learning Buddy (school-test-engine)

Desktop-App zum Üben für die Realschule (8. Klasse): KI-generierte Fragen importieren,
üben, Wissenslücken finden. Privates Projekt. Version **0.17.0** (`pyproject.toml`).

## Stack
Python ≥ 3.11 (Ziel 3.12), PySide6 (Qt), SQLite, pydantic, icalendar, pytest.
Packaging: PyInstaller + Inno Setup (Windows-Installer).

## Struktur
- `src/school_test_engine/` – Paket. Einstieg `__main__.py` → `app.py`.
  - `ui/` (Hauptfenster, `pages/`, `widgets/`, `dialogs/`, `style.qss`, `design.py`)
  - `storage/` (SQLite-Repos), `models/`, `importer/` (KI-Fragen-Import), `prompt_builder/`
  - `study/`, `daily/`, `grading/`, `error_book/`, `cockpit/` (Übungs- und Auswertungslogik)
  - `school_calendar/`, `ical_sync/` (Schulkalender/Termine), `pdf_export/`
- `tests/` – pytest (Unit + `integration/`, `fixtures/`).
- `packaging/` – `build.bat`, `learning-buddy.spec`, `installer.iss`, `README.md`.
- `docs/superpowers/` – `specs/` und `plans/` (Phasenpläne).
- `assets/`, `examples/` – Icons/Branding, Beispiel-Fragen.

## Build / Run
```bash
python -m venv .venv
.venv\Scripts\activate             # Windows  (Linux: source .venv/bin/activate)
pip install -e .[dev]
pytest -q                          # Tests
python -m school_test_engine       # App starten
./run.sh                           # Linux: legt venv bei Bedarf selbst an und startet
packaging\build.bat                # Windows-.exe/Installer, Details packaging/README.md
```

## Konventionen
- UI-Texte Deutsch, Code/Bezeichner Englisch.
- Neue Funktion: zuerst Spec/Plan unter `docs/superpowers/`, dann TDD mit pytest.
- Logik von Qt trennen (Services/Repos testbar ohne UI); UI-Tests ohne veraltete Qt-APIs.
- Datenbank (`*.sqlite3`) und `.venv/`, `build/`, `dist/` nicht einchecken.
- Commits: Conventional Commits (`fix(ui/page): …`, `docs(plan): …`), Deutsch oder Englisch.
- Version in `pyproject.toml` bei Release erhöhen.
