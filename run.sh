#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Self-heal: nach Repo-Umzügen kann das venv halb-tot sein (Shebangs auf alten
# Pfad, editable-Install zeigt auf gelöschten Source). Wenn der Import scheitert,
# venv neu aufsetzen.
needs_install=0
if [ ! -d .venv ]; then
    needs_install=1
elif ! .venv/bin/python -c "import school_test_engine" 2>/dev/null; then
    echo "venv ist beschädigt oder unvollständig — erzeuge neu..."
    rm -rf .venv
    needs_install=1
fi

if [ "$needs_install" = "1" ]; then
    echo "Erstelle Python-venv und installiere Abhängigkeiten..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -e ".[dev]"
fi

exec .venv/bin/python -m school_test_engine "$@"
