# Phase 17.5 — Windows-Distribution (PyInstaller + Inno Setup)

**Status:** Design / Spec
**Datum:** 2026-05-16
**Vorgängerphase:** Phase 17 (Schulkalender + Ferien-Banner)
**Typ:** Distribution-Infrastruktur (kein neues UI-Feature), Code-Refactor (Resource-Paths), neue Build-Pipeline

---

## 1. Motivation

Learning Buddy läuft bisher nur auf Matthias' Linux-Mint-Box als Dev-Environment. Damit Clemens (Sohn, 8. Klasse Realschule) und potenziell Verwandte/Freunde die App auf ihrem Windows-Rechner nutzen können, brauchen wir einen verteilbaren Installer.

Phase 17.5 produziert eine `setup_learning-buddy_vX.Y.Z.exe` — ein klassischer Windows-Setup-Wizard, der die App per-Maschine installiert, ein Start-Menü-Eintrag anlegt und optional eine Desktop-Verknüpfung erstellt. Distribution per E-Mail / USB / Cloud-Share. Kein App-Store, kein Auto-Update, kein Code-Signing.

## 2. Ziel

Eine Win64-`.exe` als One-File-Installer, die folgendes liefert:

- Ein-Klick-Installation in `C:\Program Files\Learning Buddy\` (Admin-Privilegien).
- Start-Menü-Eintrag „Learning Buddy" + Deinstallationsverknüpfung.
- Opt-in Desktop-Verknüpfung (Checkbox im Wizard).
- DB + User-Daten unter `%LOCALAPPDATA%\learning-buddy\` (per-User, bleibt bei Deinstallation erhalten).
- Deutscher Wizard (Inno's `German.isl`).
- Saubere Deinstallation via Systemsteuerung.

Voraussetzung beim Empfänger: Windows 10/11 64-bit. Keine vorinstallierten Tools.

## 3. Nicht-Ziele

- **Kein Auto-Update.** Neue Releases werden manuell verteilt.
- **Kein Code-Signing.** SmartScreen zeigt bei jeder neuen Version eine „Computer wurde geschützt"-Warnung. Empfänger akzeptiert via „Weitere Informationen → Trotzdem ausführen". Akzeptabel im Familien-/Freundeskreis.
- **Keine macOS-Distribution.** Pfad-Logik im Code wird macOS-fähig vorbereitet, aber kein macOS-Build-Skript.
- **Keine App-Store-/MSIX-Distribution.** Bleibt out-of-scope.
- **Kein Cross-Compile von Linux.** Build läuft ausschließlich auf einer Windows-Maschine, die der Maintainer (Matthias) zur Hand hat.
- **Keine DB-Migration von Linux nach Windows.** Frischer Profil-Anlage-Flow auf jedem neuen Windows-Install.
- **Kein Auto-Provisioning des iCal-Feeds.** Wird im Profil-Editor manuell eingetragen wie bisher.
- **Keine GitHub-Release-Automation / CI.** Build läuft lokal, Distribution manuell.

## 4. Architektur-Übersicht

```
school-test-engine/
├── packaging/                           NEU
│   ├── learning-buddy.spec              PyInstaller-Spec
│   ├── installer.iss                    Inno Setup-Script
│   ├── build.bat                        Windows-Orchestrator
│   ├── prepare_icon.py                  SVG→ICO Konvertierung (einmalig)
│   └── README.md                        Build-Anleitung
├── assets/
│   ├── icon.ico                         NEU (generiert)
│   └── … (bestehende SVG/Fonts/KaTeX)
├── src/school_test_engine/
│   ├── __init__.py                      MOD __version__ = "0.17.0"
│   ├── config.py                        MOD plattform-aware data_dir()
│   └── resources.py                     NEU app_root / assets_dir / examples_dir
├── tests/
│   ├── test_config_platform.py          NEU (4 Tests)
│   └── test_resources.py                NEU (3 Tests)
├── pyproject.toml                       MOD version 0.17.0 + [build]-extras
└── README.md                            MOD Pointer auf packaging/README.md
```

**Bundling-Flow (Windows-Maschine):**

```
1. Repo ist auf Windows verfügbar (git clone oder USB).
2. Einmalige Setup:
   - Python 3.12 64-bit installiert.
   - Inno Setup 6 installiert.
   - python -m venv .venv && pip install -e .[build]
3. packaging\build.bat ausführen:
   a) Liest __version__ aus school_test_engine/__init__.py.
   b) Ruft PyInstaller mit packaging/learning-buddy.spec auf.
      Output: dist/learning-buddy/ Ordner mit .exe + _internal/-Bundle.
   c) Ruft Inno Setup Compiler (ISCC) mit packaging/installer.iss auf.
      Übergibt /DMyAppVersion=X.Y.Z als Preprocessor-Define.
      Output: dist/setup_learning-buddy_vX.Y.Z.exe (Single-File-Installer).
4. Distribution: .exe per E-Mail / USB / Cloud-Share.
```

**Runtime-Flow (Empfänger-Maschine):**

```
1. setup_learning-buddy_vX.Y.Z.exe doppelklick.
2. SmartScreen-Warnung → "Weitere Informationen → Trotzdem ausführen" (einmalig).
3. Inno Setup-Wizard (Deutsch):
   - Willkommen → Installations-Ordner (default C:\Program Files\Learning Buddy)
     → Zusätzliche Aufgaben: [✓] Desktop-Verknüpfung (default angehakt)
     → Installation läuft → Fertig.
4. Start: Start-Menü → "Learning Buddy".
5. App legt DB an in %LOCALAPPDATA%\learning-buddy\db.sqlite3.
6. Profil-Picker erscheint, User legt erstes Profil an.
```

## 5. Code-Änderungen

### 5.1 `src/school_test_engine/config.py` — Plattform-aware data_dir()

```python
"""Per-user data location — DB + app-state. Phase 17.5: cross-platform."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    """Per-user data directory.

    Windows:  %LOCALAPPDATA%\\learning-buddy
    Linux:    $XDG_DATA_HOME/school-test-engine   (default ~/.local/share/...)
    macOS:    ~/Library/Application Support/learning-buddy
    """
    root = _platform_root()
    path = root / _app_data_folder_name()
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    """Override via SCHOOL_TEST_ENGINE_DB env var for tests."""
    override = os.environ.get("SCHOOL_TEST_ENGINE_DB")
    if override:
        return Path(override)
    return data_dir() / "db.sqlite3"


def _platform_root() -> Path:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local)
        return Path.home() / "AppData" / "Local"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg)
    return Path.home() / ".local" / "share"


def _app_data_folder_name() -> str:
    """Linux retains legacy 'school-test-engine' for backwards-compat.
    Windows + macOS use the friendly 'learning-buddy' name."""
    if sys.platform in ("win32", "darwin"):
        return "learning-buddy"
    return "school-test-engine"
```

**Backwards-Compat-Hinweis:** Linux behält den existierenden Ordnernamen `school-test-engine`, weil Matthias' bestehende DB (Phase 1-17 Inhalte) sonst gestrandet wäre. Auf Windows/macOS gibt es noch keine Bestandsdaten — daher der idiomatische Name `learning-buddy`.

### 5.2 `src/school_test_engine/resources.py` — Single Source of Truth für Asset-Pfade (NEU)

```python
"""Resource-path resolution that works in dev AND PyInstaller bundles.

Phase 17.5 — eliminates inconsistent Path(__file__).parents[N] walks across
9 modules and gracefully handles sys._MEIPASS in frozen builds.
"""
from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Directory whose direct children are 'assets/' and 'examples/'.

    Dev mode:                  <repo>/
    PyInstaller one-folder:    <bundle>/_internal/
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def assets_dir() -> Path:
    return app_root() / "assets"


def examples_dir() -> Path:
    return app_root() / "examples"
```

### 5.3 Refactor: 9 Call-Sites auf resources.py umstellen

| Datei | Vorher | Nachher |
|---|---|---|
| `app.py:21` | `Path(__file__).resolve().parents[2] / "assets" / "logomark.svg"` | `assets_dir() / "logomark.svg"` |
| `ui/main_window.py:50` | `Path(__file__).resolve().parents[3] / "assets"` | `assets_dir()` |
| `prompt_builder/template.py:8` | `Path(__file__).resolve().parents[3] / "examples" / "PROMPT-FOR-AI.md"` | `examples_dir() / "PROMPT-FOR-AI.md"` |
| `ui/pages/import_wizard.py:99` | `Path(__file__).resolve().parents[3] / "examples"` (pre-existing-Bug, parents[3]=src/ statt repo) | `examples_dir()` |
| `ui/design.py:12` | `Path(__file__).resolve().parents[2].parent / "assets" / "fonts"` | `assets_dir() / "fonts"` |
| `ui/pages/profile_picker.py:23` | `Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"` | `assets_dir() / "logomark.svg"` |
| `ui/widgets/math_view.py:9` | `Path(__file__).resolve().parents[3].parent / "assets" / "katex"` | `assets_dir() / "katex"` |
| `ui/widgets/global_header.py:27` | `Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"` | `assets_dir() / "logomark.svg"` |
| `ui/widgets/avatar_badge.py:15` | `Path(__file__).resolve().parents[3].parent / "assets" / "avatar-placeholder.svg"` | `assets_dir() / "avatar-placeholder.svg"` |

Importe in jeder Datei ergänzen:
```python
from ...resources import assets_dir  # oder ..resources, je nach Tiefe
```

### 5.4 `src/school_test_engine/__init__.py` — Version-Bump

```python
__version__ = "0.17.0"
```

### 5.5 `pyproject.toml` — Version + Build-Extras

```toml
[project]
name = "school-test-engine"
version = "0.17.0"
# … existing dependencies unverändert …

[project.optional-dependencies]
build = [
    "pyinstaller>=6.0",
    "Pillow>=10.0",
    "cairosvg>=2.7",     # nur lokal benötigt; nur für prepare_icon.py
]
```

`cairosvg` ist eine Linux-only Dev-Dependency für die einmalige Icon-Generation. Wird vom PyInstaller-Bundle ausgeschlossen (kommt nicht in Empfänger-Setup).

## 6. PyInstaller-Spec

### 6.1 `packaging/learning-buddy.spec`

```python
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Learning Buddy.

Run from the repo root:
    pyinstaller packaging/learning-buddy.spec --clean --noconfirm
Output:
    dist/learning-buddy/learning-buddy.exe + dist/learning-buddy/_internal/*
"""
import os

REPO = os.path.abspath(os.path.join(SPECPATH, ".."))

block_cipher = None


a = Analysis(
    [os.path.join(REPO, "src", "school_test_engine", "__main__.py")],
    pathex=[os.path.join(REPO, "src")],
    binaries=[],
    datas=[
        (os.path.join(REPO, "assets"), "assets"),
        (os.path.join(REPO, "examples", "PROMPT-FOR-AI.md"), "examples"),
        (os.path.join(REPO, "src", "school_test_engine", "storage", "migrations"),
         "school_test_engine/storage/migrations"),
        (os.path.join(REPO, "src", "school_test_engine", "ui", "style.qss"),
         "school_test_engine/ui"),
    ],
    hiddenimports=[
        "icalendar",
        "icalendar.compat",
        "icalendar.cal",
        "PySide6.QtSvgWidgets",
        "PySide6.QtPrintSupport",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "numpy", "pandas", "scipy",
        "PySide6.QtBluetooth", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtSensors",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="learning-buddy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX kann Qt-DLLs zerstören
    console=False,       # GUI-App, kein Terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(REPO, "assets", "icon.ico"),
)


coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="learning-buddy",
)
```

**Begründungen:**

- **Excludes:** Reduzieren Bundle-Größe deutlich. QtBluetooth/QtCharts/QtMultimedia/etc. werden nicht genutzt aber kosten ~80 MB. Zielgröße: 80-120 MB statt 250+ ohne Excludes.
- **Hidden-Imports:** `icalendar` macht dynamische Imports (intern `compat`, `cal`). PySide6.QtSvgWidgets/QtPrintSupport/QtWebEngine sicherheitshalber explizit gelistet, falls Static-Analyzer sie übersieht.
- **`upx=False`:** UPX-Kompression kann Qt-DLLs korrumpieren — bekanntes PyInstaller+PySide6-Issue.
- **One-folder mode:** Schnellerer Startup als one-file (~3s gespart), einfacher zu debuggen, kein TEMP-Entpacken bei jedem Start.

## 7. Icon-Generation

### 7.1 `packaging/prepare_icon.py` — Einmal-Skript

```python
"""Convert assets/logomark.svg → assets/icon.ico (multi-resolution)."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SVG = REPO / "assets" / "logomark.svg"
ICO = REPO / "assets" / "icon.ico"
SIZES = [16, 32, 48, 64, 128, 256]


def main() -> None:
    try:
        import cairosvg
    except ImportError:
        raise SystemExit("cairosvg not installed. Run: pip install cairosvg Pillow")

    images = []
    for size in SIZES:
        png_bytes = cairosvg.svg2png(
            url=str(SVG), output_width=size, output_height=size
        )
        images.append(Image.open(io.BytesIO(png_bytes)).convert("RGBA"))

    images[0].save(
        ICO, format="ICO",
        sizes=[(im.width, im.height) for im in images],
        append_images=images[1:],
    )
    print(f"Wrote {ICO}")


if __name__ == "__main__":
    main()
```

Output: `assets/icon.ico` (~50 KB). **Einmal lokal auf der Linux-Box laufen lassen + committen.** Wird in Folge-Builds nur erneut generiert, wenn sich `logomark.svg` ändert.

## 8. Inno Setup-Script

### 8.1 `packaging/installer.iss`

```ini
; Inno Setup script — Learning Buddy v{#MyAppVersion}
; Compile: ISCC.exe /DMyAppVersion=0.17.0 packaging\installer.iss

#ifndef MyAppVersion
  #define MyAppVersion "0.17.0"
#endif
#define MyAppName "Learning Buddy"
#define MyAppPublisher "Matthias Keßler"
#define MyAppExeName "learning-buddy.exe"

[Setup]
AppId={{8B2E4C7A-5F31-4D8E-9A6B-3C8F7D2E1A95}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=© 2026 {#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=setup_learning-buddy_v{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem &Desktop erstellen"; \
  GroupDescription: "Zusätzliche Symbole:"; Flags: unchecked

[Files]
Source: "..\dist\learning-buddy\learning-buddy.exe"; \
  DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\learning-buddy\_internal\*"; \
  DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} deinstallieren"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
  Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{#MyAppName} starten"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Bewusst leer — User-Daten in %LOCALAPPDATA%\learning-buddy\ bleiben erhalten.
```

**Wichtige Direktiven:**

- **`AppId`:** Fester GUID. Inno identifiziert damit existierende Installationen für Upgrade-Pfade. **Darf nie geändert werden** — sonst kann ein neuer Setup nicht den alten überschreiben.
- **`{autopf}`:** Erweitert zu `C:\Program Files` (64-bit). Per-Maschine-Install.
- **`PrivilegesRequired=admin`:** UAC-Prompt beim Start des Setups. Erforderlich für `{autopf}`.
- **`x64compatible`:** Verhindert Installation auf 32-bit-Windows (PySide6 ist x64-only).
- **`Compression=lzma2/ultra`:** Beste Kompression, ~30s länger beim Bauen, aber Installer-Größe ein Drittel des unkomprimierten Bundles.
- **`German.isl`:** Inno's eingebaute deutsche Wizard-Übersetzung.
- **`[UninstallDelete]` leer:** User-Daten bleiben. Wer Total-Removal will: manuell `%LOCALAPPDATA%\learning-buddy\` löschen.

## 9. Build-Orchestrator

### 9.1 `packaging/build.bat`

```bat
@echo off
setlocal enabledelayedexpansion

REM Learning Buddy — Windows Build Script
REM Run from repo root: packaging\build.bat

set REPO=%~dp0..
cd /d "%REPO%"

REM 1. Read __version__ from school_test_engine
for /f "delims=" %%v in ('python -c "from school_test_engine import __version__; print(__version__)"') do set APPVERSION=%%v
if "%APPVERSION%"=="" (
    echo [error] Could not read __version__
    exit /b 1
)
echo [build] App version: %APPVERSION%

REM 2. PyInstaller
echo [build] Running PyInstaller…
python -m PyInstaller packaging\learning-buddy.spec --clean --noconfirm
if errorlevel 1 (
    echo [error] PyInstaller failed
    exit /b 1
)

REM 3. Inno Setup
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo [error] Inno Setup 6 not found
    echo Install from: https://jrsoftware.org/isdl.php
    exit /b 1
)

echo [build] Running Inno Setup Compiler…
%ISCC% /DMyAppVersion=%APPVERSION% packaging\installer.iss
if errorlevel 1 (
    echo [error] Inno Setup compilation failed
    exit /b 1
)

echo.
echo [done] dist\setup_learning-buddy_v%APPVERSION%.exe
endlocal
```

## 10. Doku

### 10.1 `packaging/README.md` (NEU)

Build-Anleitung für die Maintainer-Maschine. Voraussetzungen, Setup-Schritte, Distribution-Hinweise, SmartScreen-Hinweis für Empfänger.

### 10.2 Top-Level `README.md` — kurzer Pointer

> **Windows-Distribution:** Build-Anleitung in `packaging/README.md`.

## 11. Test-Strategie

| Bucket | File | Tests |
|---|---|---|
| Platform-aware data_dir | `tests/test_config_platform.py` | 4 |
| Resource-Resolver | `tests/test_resources.py` | 3 |

**Test-Suite-Wachstum: 486 → ~493.**

Alle bestehenden 486 Tests müssen grün bleiben — die 9 refactorierten Module ändern nur Pfad-Konstanten, kein Behavior in Dev-Mode.

**Bewusst NICHT getestet:**
- PyInstaller-Output (nur auf Windows verifizierbar)
- Inno-Setup-Output (ISCC ist Windows-only)
- `.ico`-Datei Multi-Resolution-Container (visueller Check)
- Bundle-Größe (variiert je nach Windows-Python-Version)

## 12. Akzeptanz-Kriterien (Manual auf Windows)

1. `packaging\build.bat` läuft fehlerfrei, Output-Größe < 150 MB.
2. `setup_learning-buddy_v0.17.0.exe` startet → SmartScreen-Warnung einmalig → Setup-Wizard auf Deutsch → Installation in `C:\Program Files\Learning Buddy\`.
3. Start-Menü-Eintrag „Learning Buddy" startet die App. App-Icon im Taskbar sichtbar.
4. DB wird in `%LOCALAPPDATA%\learning-buddy\db.sqlite3` angelegt (NICHT in `Program Files`).
5. Profil-Picker erscheint, „Neuer Benutzer" funktioniert, Avatar-Foto-Upload funktioniert.
6. Test-JSON-Import + Test spielen + KaTeX-Math-Rendering funktioniert.
7. iCal-Feed-URL eintragen, Sync ausführen, Klausuren erscheinen unter „Termine", Ferien-Banner auf Hauptmenü.
8. Schulkalender-Page öffnet sich, Filter-Chips funktionieren.
9. Druck-Vorschau auf Result-Page öffnet sich.
10. Deinstallation via Systemsteuerung → Programm-Ordner ist weg, User-Daten in `%LOCALAPPDATA%` bleiben.

## 13. Risiken + offene Fragen

- **QtWebEngine im Bundle.** KaTeX braucht es; das Modul ist ~200 MB. Bleibt im Bundle. Wenn die Endgröße prohibitiv wird → alternative SVG-Math-Rendering (Phase X, out-of-scope).
- **First-Run-Antivirus-Scan.** Windows Defender scannt unsignierte EXEs beim ersten Start (5-10s gefühlte Latenz). Normal, kein Bug.
- **VC++ Redistributable.** Falls die App auf einem PC nicht startet, fehlen meist die Visual C++-Runtime-DLLs. Workaround: Inno Setup kann VCRedist mitbundeln. Erstmal nicht eingebaut — bei Real-World-Fehler nachrüsten.
- **GUID in AppId.** Der hier vorgeschlagene GUID `8B2E4C7A-5F31-4D8E-9A6B-3C8F7D2E1A95` ist random gewürfelt; bleibt **forever** stabil. Falls Matthias einen eigenen erzeugen will (per `[guid]::NewGuid()` in PowerShell), vor erstem Release ändern.
- **Pre-existing Bug** in `import_wizard.py:99` wird nebenbei gefixt (`parents[3]` zeigte auf `src/` statt repo, fallback auf `Path.home()` verschleierte das).

## 14. Bewusst out-of-scope für 17.5

- Auto-Update-Mechanismus
- Code-Signing
- macOS-Build-Pipeline (Code-Pfad ist vorbereitet)
- Microsoft Store / MSIX
- GitHub Actions CI
- DB-Sync zwischen Geräten
- Linux `.AppImage` / `.deb`-Distribution
