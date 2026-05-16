# Phase 17.5 — Windows-Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a Windows `.exe`-Installer (PyInstaller + Inno Setup) that installs Learning Buddy per-Machine on Windows 10/11 with German wizard, opt-in desktop shortcut, and per-user data under `%LOCALAPPDATA%`.

**Architecture:** Code changes are confined to plattform-aware `config.py`, a new `resources.py` resolver, and 9 refactored call-sites for asset paths. Build pipeline lives in a new `packaging/` directory with PyInstaller-spec, Inno-Setup-script, and a `build.bat` orchestrator. No new runtime features.

**Tech Stack:** Python 3.12, PySide6, PyInstaller 6.x, Inno Setup 6, Pillow + cairosvg (for icon prep). Build runs only on Windows; code changes are tested cross-platform via `monkeypatch`.

**Spec:** `docs/superpowers/specs/2026-05-16-windows-distribution-design.md`

---

## Task 1: Resource-Resolver (`resources.py` + tests)

**Files:**
- Create: `src/school_test_engine/resources.py`
- Create: `tests/test_resources.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_resources.py
"""Resource-path resolution for dev mode + PyInstaller bundles (Phase 17.5)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_app_root_dev_mode_resolves_to_repo():
    from school_test_engine.resources import app_root
    root = app_root()
    # In dev mode, repo root has these direct children
    assert (root / "src").is_dir()
    assert (root / "assets").is_dir()


def test_app_root_frozen_mode_uses_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    # Re-import to pick up the patched sys
    import importlib
    from school_test_engine import resources
    importlib.reload(resources)
    assert resources.app_root() == tmp_path


def test_assets_dir_contains_logomark():
    from school_test_engine.resources import assets_dir
    assert (assets_dir() / "logomark.svg").exists()


def test_examples_dir_contains_prompt_template():
    from school_test_engine.resources import examples_dir
    assert (examples_dir() / "PROMPT-FOR-AI.md").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_resources.py -v`
Expected: FAIL with `ModuleNotFoundError: school_test_engine.resources`.

- [ ] **Step 3: Create resources.py**

```python
# src/school_test_engine/resources.py
"""Single source of truth for resource paths.

Resolves correctly in:
- Dev mode (running from repo checkout)
- PyInstaller one-folder bundles (sys.frozen + sys._MEIPASS)
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
    # src/school_test_engine/resources.py → parents[2] = repo root
    return Path(__file__).resolve().parents[2]


def assets_dir() -> Path:
    return app_root() / "assets"


def examples_dir() -> Path:
    return app_root() / "examples"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_resources.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/resources.py tests/test_resources.py
git commit -m "feat(resources): single resolver for dev + PyInstaller bundles"
```

---

## Task 2: Refactor 9 Call-Sites to use resources.py

**Files:**
- Modify: `src/school_test_engine/app.py`
- Modify: `src/school_test_engine/ui/main_window.py`
- Modify: `src/school_test_engine/prompt_builder/template.py`
- Modify: `src/school_test_engine/ui/pages/import_wizard.py`
- Modify: `src/school_test_engine/ui/design.py`
- Modify: `src/school_test_engine/ui/pages/profile_picker.py`
- Modify: `src/school_test_engine/ui/widgets/math_view.py`
- Modify: `src/school_test_engine/ui/widgets/global_header.py`
- Modify: `src/school_test_engine/ui/widgets/avatar_badge.py`

- [ ] **Step 1: Run the full test suite to capture baseline**

Run: `pytest -q`
Expected: 486 passed (baseline). Note the count so we can confirm zero regressions after refactor.

- [ ] **Step 2: Refactor `src/school_test_engine/app.py:21`**

Find:
```python
    icon_path = Path(__file__).resolve().parents[2] / "assets" / "logomark.svg"
```

Replace with:
```python
    from .resources import assets_dir
    icon_path = assets_dir() / "logomark.svg"
```

(The `from .resources import assets_dir` may need to live at the top of the file with other imports — place it next to other relative imports; the inline-import version is acceptable if `app.py` already mixes top-level and inline imports.)

- [ ] **Step 3: Refactor `src/school_test_engine/ui/main_window.py:50`**

Find:
```python
            assets_dir = Path(__file__).resolve().parents[3] / "assets"
```

Replace with:
```python
            from ..resources import assets_dir as _assets_dir
            assets_dir = _assets_dir()
```

The local variable is reused on line 52; the alias avoids shadowing the import.

- [ ] **Step 4: Refactor `src/school_test_engine/prompt_builder/template.py:8`**

Find:
```python
    Path(__file__).resolve().parents[3] / "examples" / "PROMPT-FOR-AI.md"
```

Replace with:
```python
    examples_dir() / "PROMPT-FOR-AI.md"
```

Add at the top of the file (after existing imports):
```python
from ..resources import examples_dir
```

- [ ] **Step 5: Refactor `src/school_test_engine/ui/pages/import_wizard.py:99`**

Find:
```python
        examples = Path(__file__).resolve().parents[3] / "examples"
```

Replace with:
```python
        examples = examples_dir()
```

Add at the top (after existing imports):
```python
from ...resources import examples_dir
```

**Note:** This call-site had a pre-existing bug (`parents[3]` resolved to `src/`, not the repo root). The refactor fixes it as a side-effect.

- [ ] **Step 6: Refactor `src/school_test_engine/ui/design.py:12`**

Find:
```python
FONTS_DIR = Path(__file__).resolve().parents[2].parent / "assets" / "fonts"
```

Replace with:
```python
from ..resources import assets_dir
FONTS_DIR = assets_dir() / "fonts"
```

(Place the import next to the other imports near the top of `design.py`; remove the now-unused `from pathlib import Path` only if no other code in the module uses it.)

- [ ] **Step 7: Refactor `src/school_test_engine/ui/pages/profile_picker.py:23`**

Find:
```python
LOGOMARK_PATH = Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"
```

Replace with:
```python
from ...resources import assets_dir
LOGOMARK_PATH = assets_dir() / "logomark.svg"
```

- [ ] **Step 8: Refactor `src/school_test_engine/ui/widgets/math_view.py:9`**

Find:
```python
_KATEX_DIR = Path(__file__).resolve().parents[3].parent / "assets" / "katex"
```

Replace with:
```python
from ...resources import assets_dir
_KATEX_DIR = assets_dir() / "katex"
```

- [ ] **Step 9: Refactor `src/school_test_engine/ui/widgets/global_header.py:27`**

Find:
```python
LOGOMARK_PATH = Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"
```

Replace with:
```python
from ...resources import assets_dir
LOGOMARK_PATH = assets_dir() / "logomark.svg"
```

- [ ] **Step 10: Refactor `src/school_test_engine/ui/widgets/avatar_badge.py:15`**

Find:
```python
    Path(__file__).resolve().parents[3].parent / "assets" / "avatar-placeholder.svg"
```

Replace with:
```python
    assets_dir() / "avatar-placeholder.svg"
```

Add at the top of the file (after existing imports):
```python
from ...resources import assets_dir
```

- [ ] **Step 11: Run the full test suite — confirm zero regressions**

Run: `pytest -q`
Expected: 486 passed (same as baseline). No new failures.

Also do a quick app smoke-test: `.venv/bin/python -m school_test_engine` should still launch and render the profile picker correctly.

- [ ] **Step 12: Verify no leftover `parents[N]` asset-path resolutions**

Run: `grep -rn 'parents\[' src/school_test_engine --include='*.py' | grep -v __pycache__`

Expected output: only `resources.py` itself (line `Path(__file__).resolve().parents[2]` — that one is legitimate). No other matches. If anything else shows up, fix it the same way.

- [ ] **Step 13: Commit**

```bash
git add src/school_test_engine/app.py \
        src/school_test_engine/ui/main_window.py \
        src/school_test_engine/prompt_builder/template.py \
        src/school_test_engine/ui/pages/import_wizard.py \
        src/school_test_engine/ui/design.py \
        src/school_test_engine/ui/pages/profile_picker.py \
        src/school_test_engine/ui/widgets/math_view.py \
        src/school_test_engine/ui/widgets/global_header.py \
        src/school_test_engine/ui/widgets/avatar_badge.py
git commit -m "refactor(paths): 9 call-sites use resources.py — fixes import_wizard parents[3] bug"
```

---

## Task 3: Platform-aware `config.py`

**Files:**
- Modify: `src/school_test_engine/config.py`
- Create: `tests/test_config_platform.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config_platform.py
"""Platform-aware data_dir() for Phase 17.5 Windows-Distribution."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from school_test_engine import config


def test_db_path_respects_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("SCHOOL_TEST_ENGINE_DB", str(tmp_path / "custom.db"))
    assert config.db_path() == tmp_path / "custom.db"


def test_linux_uses_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.delenv("SCHOOL_TEST_ENGINE_DB", raising=False)
    expected = tmp_path / "school-test-engine"
    assert config.data_dir() == expected
    assert expected.exists()


def test_windows_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("SCHOOL_TEST_ENGINE_DB", raising=False)
    expected = tmp_path / "learning-buddy"
    assert config.data_dir() == expected
    assert expected.exists()


def test_macos_uses_application_support(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv("SCHOOL_TEST_ENGINE_DB", raising=False)
    expected = tmp_path / "Library" / "Application Support" / "learning-buddy"
    assert config.data_dir() == expected
    assert expected.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_platform.py -v`
Expected: most fail — current `data_dir()` only handles Linux/XDG.

- [ ] **Step 3: Replace `src/school_test_engine/config.py` with platform-aware version**

```python
"""Per-user data location — DB + app state. Phase 17.5: cross-platform."""
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
    # Linux / *nix
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg)
    return Path.home() / ".local" / "share"


def _app_data_folder_name() -> str:
    """Linux retains 'school-test-engine' (backwards-compat with existing Phase
    1-17 installs); Windows + macOS use 'learning-buddy' (idiomatic, fresh)."""
    if sys.platform in ("win32", "darwin"):
        return "learning-buddy"
    return "school-test-engine"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_config_platform.py -v`
Expected: 4 passed.

Also verify no regression elsewhere: `pytest -q` → 490 passed (was 486 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/config.py tests/test_config_platform.py
git commit -m "feat(config): platform-aware data_dir (win/macos/linux)"
```

---

## Task 4: Version bump + build-extras

**Files:**
- Modify: `src/school_test_engine/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Bump version in `src/school_test_engine/__init__.py`**

```python
__version__ = "0.17.0"
```

- [ ] **Step 2: Update `pyproject.toml`**

Change line 3 from `version = "0.1.0"` to:

```toml
version = "0.17.0"
```

Add to the `[project.optional-dependencies]` section:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]
build = [
    "pyinstaller>=6.0",
    "Pillow>=10.0",
    "cairosvg>=2.7",
]
```

- [ ] **Step 3: Verify version is readable**

Run: `.venv/bin/python -c "from school_test_engine import __version__; print(__version__)"`
Expected output: `0.17.0`.

- [ ] **Step 4: Run the full suite — confirm no regression**

Run: `pytest -q`
Expected: 490 passed.

- [ ] **Step 5: Commit**

```bash
git add src/school_test_engine/__init__.py pyproject.toml
git commit -m "chore: bump to 0.17.0 + add [build] optional-dependencies"
```

---

## Task 5: Icon generation (run on Linux dev box, commit ICO)

**Files:**
- Create: `packaging/prepare_icon.py`
- Create: `assets/icon.ico` (generated)

- [ ] **Step 1: Install build-extras locally for icon generation**

Run: `.venv/bin/pip install cairosvg Pillow`

(Pillow may already be installed; cairosvg is new. Both are tiny installs.)

If cairosvg fails to install due to missing system libs, install: `sudo apt-get install libcairo2 libcairo2-dev` (Linux Mint / Debian-based).

- [ ] **Step 2: Create `packaging/prepare_icon.py`**

```python
"""Convert assets/logomark.svg → assets/icon.ico (multi-resolution).

Run once on the dev box; commit assets/icon.ico.
Re-run only when logomark.svg changes.

Usage: .venv/bin/python packaging/prepare_icon.py
"""
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
        raise SystemExit(
            "cairosvg not installed. Run: pip install cairosvg Pillow"
        )

    images = []
    for size in SIZES:
        png_bytes = cairosvg.svg2png(
            url=str(SVG), output_width=size, output_height=size
        )
        images.append(Image.open(io.BytesIO(png_bytes)).convert("RGBA"))

    images[0].save(
        ICO,
        format="ICO",
        sizes=[(im.width, im.height) for im in images],
        append_images=images[1:],
    )
    print(f"Wrote {ICO}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the script**

Run: `.venv/bin/python packaging/prepare_icon.py`
Expected output: `Wrote /home/matthias/Dokumente/Claude/ai-projects/school-test-engine/assets/icon.ico`

- [ ] **Step 4: Verify the ICO is a valid multi-resolution container**

Run: `.venv/bin/python -c "from PIL import Image; im = Image.open('assets/icon.ico'); print(im.size, im.info.get('sizes', 'no-sizes-info'))"`
Expected: prints `(256, 256)` and a list of sizes including the 6 we generated.

File size should be roughly 30-80 KB depending on logomark complexity.

- [ ] **Step 5: Commit script + icon**

```bash
git add packaging/prepare_icon.py assets/icon.ico
git commit -m "feat(assets): icon.ico multi-resolution from logomark.svg"
```

---

## Task 6: PyInstaller spec

**Files:**
- Create: `packaging/learning-buddy.spec`

- [ ] **Step 1: Create `packaging/learning-buddy.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Learning Buddy — Phase 17.5 Windows-Distribution.

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

- [ ] **Step 2: Syntax check (run as Python script)**

The `.spec` file is valid Python with PyInstaller-specific top-level helpers (`Analysis`, `PYZ`, `EXE`, `COLLECT`, `SPECPATH`). We can't execute it without PyInstaller installed, but we can at least syntax-check:

Run: `.venv/bin/python -c "compile(open('packaging/learning-buddy.spec').read(), 'learning-buddy.spec', 'exec')"`
Expected: silent success (no SyntaxError).

- [ ] **Step 3: Commit**

```bash
git add packaging/learning-buddy.spec
git commit -m "feat(packaging): PyInstaller spec for one-folder Windows bundle"
```

---

## Task 7: Inno Setup script

**Files:**
- Create: `packaging/installer.iss`

- [ ] **Step 1: Create `packaging/installer.iss`**

```ini
; Inno Setup script — Learning Buddy v{#MyAppVersion}
; Compile: ISCC.exe /DMyAppVersion=0.17.0 packaging\installer.iss
;
; Per-machine install (admin), German wizard, opt-in desktop shortcut.

#ifndef MyAppVersion
  #define MyAppVersion "0.17.0"
#endif
#define MyAppName "Learning Buddy"
#define MyAppPublisher "Matthias Keßler"
#define MyAppExeName "learning-buddy.exe"

[Setup]
; AppId — random GUID. NEVER change after first release!
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

- [ ] **Step 2: Verify file is non-empty and well-formed**

Run: `wc -l packaging/installer.iss`
Expected: ~50 lines, no syntax issues visible. ISCC will report real syntax errors when first compiled on Windows (Task 8).

- [ ] **Step 3: Commit**

```bash
git add packaging/installer.iss
git commit -m "feat(packaging): Inno Setup installer script (DE wizard, per-machine)"
```

---

## Task 8: Build orchestrator `build.bat`

**Files:**
- Create: `packaging/build.bat`

- [ ] **Step 1: Create `packaging/build.bat`**

```bat
@echo off
setlocal enabledelayedexpansion

REM Learning Buddy — Windows Build Script
REM Run from the repo root: packaging\build.bat
REM
REM Prerequisites (one-time on the build machine):
REM   - Python 3.12 64-bit (with "Add to PATH" enabled)
REM   - Inno Setup 6  (https://jrsoftware.org/isdl.php)
REM   - This repo cloned, then: python -m venv .venv && .venv\Scripts\pip install -e .[build]

set REPO=%~dp0..
cd /d "%REPO%"

REM ---------------------------------------------------------------------
REM 1. Read __version__ from school_test_engine
REM ---------------------------------------------------------------------
for /f "delims=" %%v in ('python -c "from school_test_engine import __version__; print(__version__)"') do set APPVERSION=%%v
if "%APPVERSION%"=="" (
    echo [error] Could not read __version__ from school_test_engine
    exit /b 1
)
echo [build] App version: %APPVERSION%

REM ---------------------------------------------------------------------
REM 2. PyInstaller — Python-Bundle in dist\learning-buddy\
REM ---------------------------------------------------------------------
echo [build] Running PyInstaller…
python -m PyInstaller packaging\learning-buddy.spec --clean --noconfirm
if errorlevel 1 (
    echo [error] PyInstaller failed
    exit /b 1
)

REM ---------------------------------------------------------------------
REM 3. Inno Setup — single-file installer in dist\
REM ---------------------------------------------------------------------
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo [error] Inno Setup 6 not found at %ISCC%
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

- [ ] **Step 2: Verify file is well-formed (Linux-side syntax check)**

Run: `wc -l packaging/build.bat` — expect ~50 lines.

Real test happens on the Windows build machine when running it.

- [ ] **Step 3: Make sure Git stores it with CRLF line-endings (recommended for `.bat`)**

Add to (or verify in) `.gitattributes` at repo root:

```
*.bat text eol=crlf
*.iss text eol=crlf
*.spec text eol=lf
```

If `.gitattributes` doesn't exist yet, create it with the above content.

- [ ] **Step 4: Commit**

```bash
git add packaging/build.bat .gitattributes
git commit -m "feat(packaging): build.bat orchestrator + .gitattributes for crlf"
```

---

## Task 9: Documentation

**Files:**
- Create: `packaging/README.md`
- Modify: `README.md` (top-level)

- [ ] **Step 1: Create `packaging/README.md`**

```markdown
# Learning Buddy — Windows Build

## Voraussetzungen (einmalig auf der Windows-Maschine)

1. **Python 3.12** (64-bit) von https://www.python.org — beim Installieren
   „Add Python to PATH" anhaken.
2. **Inno Setup 6** von https://jrsoftware.org/isdl.php — Default-Optionen.
3. **Git** (optional) — falls du das Repo klonen statt USB-kopieren willst.

## Setup (einmalig pro Repo-Checkout)

```powershell
cd C:\pfad\zu\school-test-engine
python -m venv .venv
.venv\Scripts\activate
pip install -e .[build]
```

## Build

```powershell
packaging\build.bat
```

Dauer: ~2-5 Minuten je nach Maschine. Output: `dist\setup_learning-buddy_v0.17.0.exe`
(~80-120 MB single-file Installer).

## Distribution

Den `setup_learning-buddy_vX.Y.Z.exe` per E-Mail, USB-Stick oder Cloud-Share
(WeTransfer, OneDrive, Google Drive) an die Empfänger schicken.

### SmartScreen-Hinweis für Empfänger

> Windows zeigt beim ersten Start eine blaue Warnung
> „Der Computer wurde durch Windows geschützt".
> Klick auf „Weitere Informationen" → „Trotzdem ausführen".
>
> Das Installer ist nicht signiert (Code-Signing-Zertifikat kostet 200-400 €/Jahr,
> nicht sinnvoll für privat). Einmaliger Klick pro Version.

## Was wo landet

| Ort | Inhalt |
|---|---|
| `C:\Program Files\Learning Buddy\` | App-Binary + Qt-DLLs + Assets (alle Windows-User können starten) |
| `%LOCALAPPDATA%\learning-buddy\` | DB + Profile + Avatar-Bilder (pro Windows-User isoliert) |
| Start-Menü → „Learning Buddy" | Start-Verknüpfung + Deinstallation |
| Desktop | Optional (Wizard-Checkbox) |

## Deinstallation

Systemsteuerung → Programme → „Learning Buddy" → Deinstallieren.

User-Daten in `%LOCALAPPDATA%\learning-buddy\` bleiben **erhalten** (für
spätere Re-Installs). Wer Total-Removal will, löscht den Ordner manuell.

## Icon-Refresh (selten nötig)

Wenn sich `assets/logomark.svg` ändert:

```bash
# Auf der Linux/macOS-Dev-Maschine:
pip install cairosvg Pillow
python packaging/prepare_icon.py
git add assets/icon.ico
git commit -m "chore(assets): regenerate icon.ico"
```

## Bekannte Stolpersteine

- **„Python wird nicht gefunden"** — Python-Installer ausgeführt ohne „Add to PATH".
  Neuer Python-Installer mit angehakter PATH-Option installieren.
- **„VC++ Runtime fehlt" beim Start auf Empfänger-PC** — Microsoft Visual C++
  Redistributable 2015-2022 (x64) von Microsoft herunterladen + installieren.
  Wird selten gebraucht (Windows 10/11 hat es meistens schon).
- **First-Run-Antivirus-Scan** — Windows Defender scannt die `.exe` beim
  ersten Start 5-10 Sekunden lang. Gefühlte Startlatenz. Normal.
```

- [ ] **Step 2: Update top-level `README.md`**

Find the existing top-level README. Add a section near the end (or wherever installation/distribution info logically fits):

```markdown
## Windows-Distribution

Build-Anleitung für die `.exe`-Installer-Erzeugung: siehe [`packaging/README.md`](packaging/README.md).
```

If the top-level README doesn't have an „Installation"-style section yet, just append this section before the final separator.

- [ ] **Step 3: Verify the packaging README renders sensibly**

Open `packaging/README.md` in any markdown viewer (or use `cat`) and skim — should be self-contained, no broken refs.

- [ ] **Step 4: Commit**

```bash
git add packaging/README.md README.md
git commit -m "docs(packaging): Windows build + distribution instructions"
```

---

## Task 10: Manual acceptance on Windows

**No code changes — this is the validation step that completes the phase.**

**Prerequisites:**
- A Windows 10/11 64-bit machine.
- Repo cloned/copied to that machine.
- Python 3.12 64-bit installed with PATH enabled.
- Inno Setup 6 installed.

**Acceptance checklist (tick off as each step succeeds):**

- [ ] **Step 1: Setup the venv on Windows**

```powershell
cd C:\path\to\school-test-engine
python -m venv .venv
.venv\Scripts\activate
pip install -e .[build]
```

Expected: pip installs without errors. PyInstaller 6.x and Pillow appear in the venv.

- [ ] **Step 2: Run the test suite on Windows**

```powershell
.venv\Scripts\pytest -q
```

Expected: 490/490 passed (same as Linux). This validates that the Phase-17.5 platform-aware code works correctly on a real Windows host.

- [ ] **Step 3: Run the build**

```powershell
packaging\build.bat
```

Expected: prints `[build] App version: 0.17.0`, runs PyInstaller (~30-90 seconds), then Inno Setup (~30 seconds), then `[done] dist\setup_learning-buddy_v0.17.0.exe`. Final file size: 80-150 MB.

- [ ] **Step 4: Inspect bundle**

Confirm `dist\learning-buddy\learning-buddy.exe` exists and `dist\learning-buddy\_internal\` contains:
- `assets\logomark.svg`, `assets\icon.ico`, `assets\fonts\*.woff2`, `assets\katex\`
- `school_test_engine\storage\migrations\*.sql` (all 012 migration files)
- `school_test_engine\ui\style.qss`

- [ ] **Step 5: Run the bundled `.exe` directly (before installer test)**

Double-click `dist\learning-buddy\learning-buddy.exe`. Expected: App starts, Profile-Picker visible. Creates `%LOCALAPPDATA%\learning-buddy\db.sqlite3` on first run. Confirm DB exists after closing the app.

- [ ] **Step 6: Run the installer**

Double-click `dist\setup_learning-buddy_v0.17.0.exe`. Expected:
- SmartScreen warning → „Weitere Informationen → Trotzdem ausführen" (one-time).
- UAC prompt (admin required for per-machine).
- German Setup-Wizard appears.
- Default install path: `C:\Program Files\Learning Buddy\`.
- „Verknüpfung auf dem Desktop erstellen" checkbox is unchecked (opt-in).
- Click „Installieren" → progress bar → „Setup wurde abgeschlossen" → launch app (optional).

- [ ] **Step 7: Verify installation artifacts**

Confirm presence of:
- `C:\Program Files\Learning Buddy\learning-buddy.exe`
- `C:\Program Files\Learning Buddy\_internal\` (full bundle contents)
- Start menu: „Learning Buddy" (folder with app shortcut + uninstaller shortcut)
- Optional: Desktop shortcut if checkbox was ticked
- Registry: Inno-managed uninstall entry visible in „Programs and Features"

- [ ] **Step 8: Full UX smoke test of the installed app**

Start app from Start-Menu shortcut. Run through:
1. New profile creation → Avatar photo upload (Phase 6C).
2. Test-JSON-Import → spielen → KaTeX-Math-Rendering (Phase 3) funktioniert.
3. iCal-Feed-URL eintragen → Sync → Klausuren erscheinen in „Termine" (Phase 15).
4. Schulkalender-Page öffnen (Logo-Menü → „Schulkalender") → Filter durchklicken (Phase 17).
5. Ferien-Banner auf Hauptmenü erscheint nach Sync (Phase 17).
6. Result-Page → Druck-Vorschau öffnet (Phase 5).

Expected: alles funktioniert ohne Crashes oder fehlende Ressourcen-Fehler.

- [ ] **Step 9: Verify DB location**

Open Explorer, navigate to `%LOCALAPPDATA%\learning-buddy\`. Expected: `db.sqlite3` is here (NOT in `Program Files\Learning Buddy`).

- [ ] **Step 10: Verify uninstall preserves user data**

Systemsteuerung → Programme → „Learning Buddy" → Deinstallieren. Expected:
- `C:\Program Files\Learning Buddy\` is removed.
- Start-Menu entry is removed.
- `%LOCALAPPDATA%\learning-buddy\db.sqlite3` **bleibt** (intentional — preserves user data for re-install).

- [ ] **Step 11: Re-install test**

Double-click the setup again → install → start app. Expected: previous DB is reused; existing profiles + data still there.

- [ ] **Step 12: Report acceptance status**

If all 11 steps above pass, Phase 17.5 is complete. Document any deviations in a final commit message:

```bash
# (No new commit needed if everything passes — just confirm acceptance.)
git log --oneline 6d527a7..HEAD   # review all Phase 17.5 commits
```

---

## Self-Review

**Spec coverage:**

- §5.1 config.py platform-aware → Task 3 ✓
- §5.2 resources.py → Task 1 ✓
- §5.3 9 call-site refactor → Task 2 ✓ (all 9 listed with exact find/replace pairs)
- §5.4 __init__.py version bump → Task 4 ✓
- §5.5 pyproject.toml build-extras → Task 4 ✓
- §6 PyInstaller spec → Task 6 ✓
- §7 Icon generation → Task 5 ✓
- §8 Inno Setup script → Task 7 ✓
- §9 Build orchestrator → Task 8 ✓
- §10.1 packaging/README.md → Task 9 ✓
- §10.2 top-level README pointer → Task 9 ✓
- §11 Test strategy (test_config_platform.py + test_resources.py) → Tasks 1 + 3 ✓
- §12 Acceptance criteria → Task 10 (manual) ✓

All spec sections covered.

**Placeholder scan:** No "TBD" / "TODO" / "implement later" in the plan. Every code block is complete.

**Type consistency:** Function names (`app_root`, `assets_dir`, `examples_dir`, `data_dir`, `db_path`, `_platform_root`, `_app_data_folder_name`) match between Task 1, Task 3, and the refactor calls in Task 2. PyInstaller-spec variables (`REPO`, `block_cipher`, `a`, `pyz`, `exe`, `coll`) match between Task 6 step 1 and the Inno Setup expectations in Task 7. Build.bat variables (`APPVERSION`, `ISCC`) match between Task 8 and Task 10's expected output.

**Note on Task 10:** It is the only fully-manual task — depends on a Windows machine being available. The plan deliberately does not require this for "phase complete" status if Matthias is not yet at a Windows host. The Linux-side code changes (Tasks 1-9) can be committed and treated as Phase-17.5-Code-Ready; Task 10 finalizes when Windows access is available.
