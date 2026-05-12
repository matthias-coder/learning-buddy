from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

_KATEX_DIR = Path(__file__).resolve().parents[3].parent / "assets" / "katex"
_KATEX_INDEX = _KATEX_DIR / "index.html"


def katex_available() -> bool:
    return _KATEX_INDEX.exists()


class MathView(QWebEngineView):
    """Webview, das LaTeX über KaTeX rendert. Eine Instanz reicht pro Seite;
    Inhalt wird per JS-Call ausgetauscht."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(220)
        self.setContextMenuPolicy(self.contextMenuPolicy().NoContextMenu)
        self._ready = False
        self._pending: str | None = None
        self.loadFinished.connect(self._on_loaded)
        if katex_available():
            self.load(QUrl.fromLocalFile(str(_KATEX_INDEX)))
        else:
            self.setHtml(
                "<body style='font-family:monospace;color:#b91c1c'>"
                "KaTeX-Assets fehlen (assets/katex/index.html nicht gefunden)."
                "</body>"
            )

    def _on_loaded(self, ok: bool) -> None:
        self._ready = bool(ok)
        if self._ready and self._pending is not None:
            latex = self._pending
            self._pending = None
            self.render_math(latex)

    def render_math(self, latex: str) -> None:
        if not self._ready:
            self._pending = latex
            return
        escaped = json.dumps(latex)

        def adjust_height(content_height):
            try:
                h = int(content_height)
            except (TypeError, ValueError):
                return
            target = max(80, min(220, h + 4))
            self.setMinimumHeight(target)
            self.setMaximumHeight(target)

        self.page().runJavaScript(f"renderMath({escaped});", adjust_height)
