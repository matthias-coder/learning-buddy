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
