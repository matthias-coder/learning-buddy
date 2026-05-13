import pytest
from pathlib import Path

from school_test_engine.prompt_builder import template


def test_load_base_prompt_strips_todo_section():
    prompt = template.load_base_prompt()
    assert "## TODO MATTHIAS" not in prompt
    assert "<dein Stil-Briefing hier>" not in prompt


def test_load_base_prompt_strips_anhaengen_section():
    prompt = template.load_base_prompt()
    assert "## Anhängen am Ende" not in prompt
    assert "Fach: <z.B. Mathe>" not in prompt


def test_load_base_prompt_keeps_aufgabe_section():
    prompt = template.load_base_prompt()
    assert "## Aufgabe" in prompt
    assert "8. Klasse Realschule" in prompt


def test_load_base_prompt_keeps_schema_section():
    prompt = template.load_base_prompt()
    assert "## Schema" in prompt
    assert "schema_version" in prompt


def test_load_base_prompt_keeps_regeln_section():
    prompt = template.load_base_prompt()
    assert "## Regeln" in prompt
    assert "topic" in prompt


def test_load_base_prompt_falls_back_when_file_missing(monkeypatch, tmp_path):
    # Point to a non-existent path
    monkeypatch.setattr(template, "_PROMPT_PATH", tmp_path / "missing.md")
    prompt = template.load_base_prompt()
    # Backup must contain Schema definition at minimum
    assert "schema_version" in prompt
    assert "## Aufgabe" in prompt
