#!/usr/bin/env bash
# Installiere school-test-engine.desktop nach ~/.local/share/applications/,
# damit die App im Startmenü auftaucht.

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${HOME}/.local/share/applications"
TARGET="${TARGET_DIR}/school-test-engine.desktop"

mkdir -p "$TARGET_DIR"

sed "s|__PROJECT_DIR__|${PROJECT_DIR}|g" \
    "${PROJECT_DIR}/school-test-engine.desktop" > "$TARGET"

chmod +x "$TARGET"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$TARGET_DIR" 2>/dev/null || true
fi

echo "✓ Installiert: $TARGET"
echo "  Du findest 'Learning Buddy' jetzt im Startmenü unter Bildung/Lernen."
