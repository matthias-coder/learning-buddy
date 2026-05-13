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
    assert "Übungs-Test" in prompt


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


def test_load_base_prompt_contains_token_placeholders():
    prompt = template.load_base_prompt()
    # Aufgabe section
    assert "{{grade}}" in prompt
    assert "{{school_type}}" in prompt
    assert "{{bundesland}}" in prompt
    assert "{{school_name}}" in prompt
    assert "{{school_year}}" in prompt
    # Schema section also has grade + school_type placeholders
    assert prompt.count("{{grade}}") >= 2
    assert prompt.count('"{{school_type}}"') >= 1


def test_load_base_prompt_no_longer_has_hardcoded_8_realschule():
    prompt = template.load_base_prompt()
    # The old hardcoded phrase must be gone
    assert "8. Klasse Realschule" not in prompt


def test_backup_template_also_uses_tokens(monkeypatch, tmp_path):
    monkeypatch.setattr(template, "_PROMPT_PATH", tmp_path / "missing.md")
    backup = template.load_base_prompt()
    assert "{{grade}}" in backup
    assert "{{school_type}}" in backup
