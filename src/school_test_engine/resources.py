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
