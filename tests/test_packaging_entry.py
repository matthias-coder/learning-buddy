"""The PyInstaller entry script runs as a top-level script, not as a package
module, so it must not use relative imports (ImportError in the frozen exe)."""
from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "packaging" / "learning-buddy.spec"


def _entry_script() -> Path:
    match = re.search(r"Analysis\(\s*\[os\.path\.join\(REPO,\s*([^\]]+?)\)\]", SPEC.read_text(encoding="utf-8"))
    assert match, "could not find entry script in Analysis([...])"
    parts = [p.strip().strip("\"'") for p in match.group(1).split(",")]
    return REPO.joinpath(*parts)


def test_entry_script_exists():
    assert _entry_script().is_file()


def test_entry_script_has_no_relative_imports():
    tree = ast.parse(_entry_script().read_text(encoding="utf-8"))
    relative = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level > 0]
    assert not relative, f"relative imports break the frozen exe: line {relative[0].lineno}"
