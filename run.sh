#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "Erste Ausführung: erstelle Python-venv und installiere Abhängigkeiten..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -e ".[dev]"
fi

exec .venv/bin/python -m school_test_engine "$@"
