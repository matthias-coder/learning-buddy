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
