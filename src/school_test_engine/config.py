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
