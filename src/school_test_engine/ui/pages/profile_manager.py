from __future__ import annotations

import sqlite3
from datetime import datetime

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...storage import users_repo
from .._format import fmt_dt
from .._layouts import clear_layout, row_get
from ..design import FontFamily
from ..widgets.avatar_badge import AvatarBadge
from ..widgets.eyebrow import Eyebrow
from ..widgets.pill import Pill
from ..widgets.shadow import apply_warm_shadow


class _ProfileRow(QFrame):
    def __init__(self, user_row, *, on_edit, on_delete, is_active: bool):
        super().__init__()
        self.setObjectName("profileRow")
        apply_warm_shadow(self, blur=10, dy=2, alpha=0.05)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        avatar = AvatarBadge(
            emoji=user_row["avatar"],
            image_bytes=row_get(user_row, "avatar_image"),
            diameter=56,
        )
        layout.addWidget(avatar)

        mid = QVBoxLayout()
        mid.setSpacing(4)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_lbl = QLabel(user_row["name"])
        name_lbl.setFont(QFont(FontFamily.DISPLAY, 16, QFont.Weight.Medium))
        name_lbl.setStyleSheet("color: #1e1b15;")
        name_row.addWidget(name_lbl)
        if is_active:
            name_row.addWidget(Pill("AKTIV", "tea"))
        name_row.addStretch(1)
        mid.addLayout(name_row)

        meta_parts: list[str] = []
        bd = row_get(user_row, "birthday")
        if bd:
            age = _age_from_iso(bd)
            if age is not None:
                meta_parts.append(f"{_fmt_birthday(bd)} · {age} Jahre")
            else:
                meta_parts.append(_fmt_birthday(bd))
        meta_parts.append(f"Angelegt {fmt_dt(user_row['created_at'])}")
        meta = QLabel("  ·  ".join(meta_parts))
        meta.setStyleSheet("color: #6f6757; font-size: 10pt;")
        mid.addWidget(meta)
        layout.addLayout(mid, stretch=1)

        edit_btn = QPushButton("Bearbeiten")
        edit_btn.setObjectName("text")
        edit_btn.clicked.connect(on_edit)
        layout.addWidget(edit_btn)
        del_btn = QPushButton("Löschen")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(on_delete)
        layout.addWidget(del_btn)


class ProfileManagerPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._return_to = "picker"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 30, 40, 30)
        outer.setSpacing(14)

        outer.addWidget(Eyebrow("Einstellungen"))
        title = QLabel("Profile verwalten")
        title.setObjectName("title")
        title.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Medium))
        outer.addWidget(title)

        lede = QLabel(
            "Hier kannst du Profile anlegen, umbenennen oder löschen — Fotos und "
            "Geburtstage gehören zum Profil."
        )
        lede.setStyleSheet("color: #4a4538;")
        lede.setWordWrap(True)
        outer.addWidget(lede)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        add = QPushButton("+  Neues Profil anlegen")
        add.setObjectName("text")
        add.clicked.connect(self._create)
        action_row.addWidget(add)
        outer.addLayout(action_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.scroll.setWidget(self.list_container)
        outer.addWidget(self.scroll, stretch=1)

    def show_for(self, return_to: str) -> None:
        self._return_to = return_to
        self.reload()

    def reload(self) -> None:
        clear_layout(self.list_layout)

        users = users_repo.list_users(self.conn)
        for u in users:
            uid = int(u["id"])
            row = _ProfileRow(
                u,
                on_edit=lambda _=False, _uid=uid: self._edit(_uid),
                on_delete=lambda _=False, _uid=uid: self._delete(_uid),
                is_active=(self.window.active_user_id == uid),
            )
            row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch(1)

    def _create(self) -> None:
        self.window.show_profile_edit(user_id=None, return_to="manager")

    def _edit(self, user_id: int) -> None:
        self.window.show_profile_edit(user_id=user_id, return_to="manager")

    def _delete(self, user_id: int) -> None:
        if self.window.active_user_id == user_id:
            QMessageBox.information(
                self, "Geht nicht",
                "Du benutzt dieses Profil gerade — wechsle erst auf ein anderes.",
            )
            return
        if users_repo.count_users(self.conn) <= 1:
            QMessageBox.information(
                self, "Geht nicht",
                "Es muss mindestens ein Profil übrig bleiben.",
            )
            return
        u = users_repo.get_user(self.conn, user_id)
        if u is None:
            return
        counts = self.conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM tests WHERE user_id = ?) AS n_tests,
                (SELECT COUNT(*) FROM attempts WHERE user_id = ?) AS n_attempts
            """,
            (user_id, user_id),
        ).fetchone()
        msg = (
            f"Wirklich '{u['name']}' löschen?\n\n"
            f"{counts['n_tests']} Test(s) und {counts['n_attempts']} Versuch(e) gehen "
            "dabei verloren — das kann nicht rückgängig gemacht werden."
        )
        reply = QMessageBox.question(
            self, "Profil löschen?", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            users_repo.delete_user(self.conn, user_id)
            self.reload()

    def _back(self) -> None:
        if self._return_to == "menu":
            self.window.show_menu()
        else:
            self.window.show_profile_picker()


def _fmt_birthday(iso: str | None) -> str:
    if not iso:
        return "—"
    parts = iso.split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return iso


def _age_from_iso(iso: str) -> int | None:
    try:
        parts = iso.split("-")
        if len(parts) != 3:
            return None
        birth = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
        today = datetime.now()
        age = today.year - birth.year - (
            (today.month, today.day) < (birth.month, birth.day)
        )
        if 0 <= age <= 130:
            return age
    except (ValueError, TypeError):
        pass
    return None
