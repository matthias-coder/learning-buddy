"""Shared action-card widget — used by the Cockpit grid and the
'Test erstellen' landing page."""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from ..design import Color, FontFamily, Semantic
from .clickable_card import ClickableCard


def make_action_card(eyebrow_text: str, title_text: str, description: str) -> ClickableCard:
    card = ClickableCard(object_name="actionCard")
    card.setMinimumSize(340, 150)
    card.setMaximumHeight(180)
    card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(22, 18, 22, 16)
    layout.setSpacing(6)

    eyebrow = QLabel(eyebrow_text)
    eyebrow.setObjectName("eyebrow")
    layout.addWidget(eyebrow)

    title = QLabel(title_text)
    title.setObjectName("h2")
    title.setFont(QFont(FontFamily.DISPLAY, 18, QFont.Weight.Medium))
    title.setWordWrap(True)
    title.setStyleSheet(f"color: {Semantic.FG};")
    layout.addWidget(title)

    desc = QLabel(description)
    desc.setStyleSheet(f"color: {Color.PAPER_600}; font-size: 10pt;")
    desc.setWordWrap(True)
    layout.addWidget(desc)

    layout.addStretch(1)
    arrow_row = QHBoxLayout()
    arrow_row.addStretch(1)
    arrow = QLabel("→")
    arrow.setStyleSheet(f"color: {Semantic.ACCENT}; font-size: 16pt; font-weight: 600;")
    arrow_row.addWidget(arrow)
    layout.addLayout(arrow_row)
    return card
