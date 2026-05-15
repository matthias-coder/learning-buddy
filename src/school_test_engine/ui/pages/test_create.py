"""'Test erstellen' landing page — two paths: KI-generieren or Datei-importieren."""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..design import FontFamily, Semantic, Spacing
from ..widgets.action_card import make_action_card


class TestCreatePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(Spacing.S4)

        # Header
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self.window.show_menu)
        head.addWidget(back)
        head.addStretch(1)
        outer.addLayout(head)

        eyebrow = QLabel("ERSTELLEN")
        eyebrow.setObjectName("eyebrow")
        outer.addWidget(eyebrow)

        title = QLabel("Test erstellen")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        outer.addWidget(title)

        subtitle = QLabel("Wie willst du den nächsten Test bauen?")
        subtitle.setStyleSheet(f"color: {Semantic.FG_MUTED};")
        outer.addWidget(subtitle)

        outer.addSpacing(Spacing.S4)

        # Two action cards side-by-side
        cards_row = QHBoxLayout()
        cards_row.setSpacing(Spacing.S4)

        ki = make_action_card(
            "KI",
            "Per KI generieren",
            "Prompt erzeugen, in ChatGPT/Claude einfügen — JSON zurück importieren",
        )
        ki.clicked.connect(self._open_prompt_builder)
        cards_row.addWidget(ki)

        datei = make_action_card(
            "DATEI",
            "Aus JSON importieren",
            "Fertige JSON-Datei mit Fragen einlesen",
        )
        datei.clicked.connect(self._open_import)
        cards_row.addWidget(datei)

        outer.addLayout(cards_row)
        outer.addStretch(1)

    def _open_prompt_builder(self) -> None:
        self.window.show_prompt_builder()

    def _open_import(self) -> None:
        self.window.show_import()
