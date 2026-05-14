from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...storage import attempts_repo, users_repo
from ..design import FontFamily
from ..widgets.flow_layout import FlowLayout
from ..widgets.profile_card import ProfileCard


LOGOMARK_PATH = Path(__file__).resolve().parents[3].parent / "assets" / "logomark.svg"


class ProfilePickerPage(QWidget):
    """Startseite: Auswahl des aktiven Profils. Netflix-Stil."""

    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn

        outer = QVBoxLayout(self)
        outer.setContentsMargins(60, 60, 60, 40)
        outer.setSpacing(24)

        # Header mit Logomark
        header = QVBoxLayout()
        header.setSpacing(10)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if LOGOMARK_PATH.exists():
            logo = QSvgWidget(str(LOGOMARK_PATH))
            logo.setFixedSize(QSize(64, 64))
            logo_row = QHBoxLayout()
            logo_row.addStretch(1)
            logo_row.addWidget(logo)
            logo_row.addStretch(1)
            header.addLayout(logo_row)

        eyebrow = QLabel("die Kessler Familie")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        eyebrow.setStyleSheet("color: #6f6757; letter-spacing: 1.5pt;")
        header.addWidget(eyebrow)
        title = QLabel("Wer übt heute?")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 40, QFont.Weight.Normal))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(title)
        outer.addLayout(header)
        outer.addSpacing(8)

        # FlowLayout in einem zentrierten Container — KEIN stretch=1, sonst dehnen sich Karten
        grid_row = QHBoxLayout()
        grid_row.addStretch(1)
        self.grid_container = QWidget()
        self.grid = FlowLayout(h_spacing=20, v_spacing=20)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid_container.setLayout(self.grid)
        grid_row.addWidget(self.grid_container)
        grid_row.addStretch(1)
        outer.addLayout(grid_row)
        outer.addStretch(1)

        # Footer-Link
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.manage_btn = QPushButton("Profile verwalten →")
        self.manage_btn.setObjectName("text")
        self.manage_btn.clicked.connect(self._open_manager)
        footer.addWidget(self.manage_btn)
        outer.addLayout(footer)

    def reload(self) -> None:
        # Layout leeren
        while self.grid.count():
            it = self.grid.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

        users = users_repo.list_users(self.conn)
        for u in users:
            meta = self._meta_for(int(u["id"]))
            try:
                img = u["avatar_image"]
            except (IndexError, KeyError):
                img = None
            card = ProfileCard(
                avatar=u["avatar"], name=u["name"], meta=meta, image_bytes=img,
            )
            card.clicked.connect(lambda _uid=int(u["id"]): self._pick(_uid))
            self.grid.addWidget(card)

        # "+ Neues Profil"-Kachel als letzte
        plus = ProfileCard(avatar="+", name="Neues Profil", plus=True)
        plus.clicked.connect(
            lambda: self.window.show_profile_edit(user_id=None, return_to="picker")
        )
        self.grid.addWidget(plus)

    def _meta_for(self, user_id: int) -> str:
        n = self.conn.execute(
            "SELECT COUNT(*) FROM attempts WHERE user_id = ? AND completed = 1",
            (user_id,),
        ).fetchone()[0]
        if n == 0:
            return "noch keine Versuche"
        if n == 1:
            return "1 Versuch"
        return f"{n} Versuche"

    def _pick(self, user_id: int) -> None:
        self.window.set_active_user(user_id)

    def _open_manager(self) -> None:
        self.window.show_profile_manager(return_to="picker")
