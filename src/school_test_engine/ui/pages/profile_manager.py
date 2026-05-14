from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QDate, QIODevice, Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...prompt_builder.school_context import BUNDESLAENDER, SCHOOL_TYPES
from ...storage import users_repo
from .._format import fmt_dt
from .._layouts import clear_layout, row_get
from ..design import FontFamily
from ..widgets.avatar_badge import AvatarBadge
from ..widgets.avatar_tile import AvatarTile
from ..widgets.eyebrow import Eyebrow
from ..widgets.pill import Pill
from ..widgets.shadow import apply_warm_shadow


COMMON_AVATARS = [
    "👤", "🧒", "👧", "🧑", "👨", "👩",
    "🦊", "🐱", "🐶", "🐻", "🌟", "🎓",
]


@dataclass
class ProfileValues:
    name: str
    avatar: str
    avatar_image: bytes | None
    birthday: str | None
    ai_style_briefing: str | None
    grade: int | None
    school_type: str | None
    bundesland: str | None
    school_name: str | None
    school_year: str | None


def _pixmap_to_png_bytes(pm: QPixmap, max_dim: int = 256) -> bytes:
    if pm.width() > max_dim or pm.height() > max_dim:
        pm = pm.scaled(
            max_dim, max_dim,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pm.save(buf, "PNG")
    return bytes(ba.data())


class _ProfileEditDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        initial_name: str = "",
        initial_avatar: str = "👤",
        initial_image: bytes | None = None,
        initial_birthday: str | None = None,
        initial_style_briefing: str | None = None,
        initial_grade: int | None = None,
        initial_school_type: str | None = None,
        initial_bundesland: str | None = None,
        initial_school_name: str | None = None,
        initial_school_year: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Profil bearbeiten" if initial_name else "Neues Profil")
        self.setMinimumWidth(420)
        self.setMaximumWidth(620)
        self._selected_avatar = initial_avatar
        self._avatar_image: bytes | None = initial_image
        self._tiles: list[AvatarTile] = []
        self._birthday_set = initial_birthday is not None

        outer = QVBoxLayout(self)
        outer.setSpacing(14)
        outer.setContentsMargins(24, 24, 24, 20)

        outer.addWidget(Eyebrow("Name"))
        self.name_edit = QLineEdit(initial_name)
        self.name_edit.setPlaceholderText("z.B. Clemens")
        outer.addWidget(self.name_edit)

        bd_outer = QHBoxLayout()
        bd_left = QVBoxLayout()
        bd_left.addWidget(Eyebrow("Geburtstag (optional)"))
        self.birthday_edit = QDateEdit()
        self.birthday_edit.setCalendarPopup(True)
        self.birthday_edit.setDisplayFormat("dd.MM.yyyy")
        initial_qdate = _parse_iso_date(initial_birthday)
        self.birthday_edit.setDate(initial_qdate or QDate(2010, 1, 1))
        # connect erst NACH setDate, sonst feuert dateChanged beim Initialisieren
        self.birthday_edit.dateChanged.connect(self._on_birthday_edited)
        bd_left.addWidget(self.birthday_edit)
        bd_outer.addLayout(bd_left, stretch=1)
        clear_bd = QPushButton("zurücksetzen")
        clear_bd.setObjectName("text")
        clear_bd.clicked.connect(self._clear_birthday)
        bd_right = QVBoxLayout()
        bd_right.addSpacing(20)
        bd_right.addWidget(clear_bd)
        bd_outer.addLayout(bd_right)
        outer.addLayout(bd_outer)

        outer.addWidget(Eyebrow("Avatar"))
        tiles_grid = QGridLayout()
        tiles_grid.setSpacing(8)
        for idx, emoji in enumerate(COMMON_AVATARS):
            tile = AvatarTile(emoji)
            tile.clicked.connect(self._set_emoji)
            tile.set_selected(emoji == initial_avatar and not initial_image)
            self._tiles.append(tile)
            tiles_grid.addWidget(tile, idx // 6, idx % 6)
        outer.addLayout(tiles_grid)

        photo_row = QHBoxLayout()
        photo_row.setSpacing(8)
        upload = QPushButton("📷  Foto hochladen …")
        upload.clicked.connect(self._upload_photo)
        photo_row.addWidget(upload)
        self._remove_btn = QPushButton("Foto entfernen")
        self._remove_btn.setObjectName("text")
        self._remove_btn.clicked.connect(self._remove_photo)
        if not initial_image:
            self._remove_btn.hide()
        photo_row.addWidget(self._remove_btn)
        photo_row.addStretch(1)
        outer.addLayout(photo_row)

        preview_row = QHBoxLayout()
        preview_row.addStretch(1)
        self.preview = AvatarBadge(
            emoji=self._selected_avatar,
            image_bytes=self._avatar_image,
            diameter=100,
        )
        preview_row.addWidget(self.preview)
        preview_row.addStretch(1)
        outer.addLayout(preview_row)

        # Style-Briefing for the AI prompt generator (Phase 8)
        style_label = QLabel("KI-Stil-Hinweis (optional)")
        style_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
        outer.addWidget(style_label)

        self.style_edit = QPlainTextEdit()
        self.style_edit.setPlaceholderText(
            "z. B.: Schreibstil: Du-Form, freundlich.\n"
            "Mathe: saubere Äquivalenzumformungen in der Erklärung."
        )
        self.style_edit.setMaximumHeight(110)
        if initial_style_briefing:
            self.style_edit.setPlainText(initial_style_briefing)
        outer.addWidget(self.style_edit)

        # Schul-Kontext (Phase 9)
        ctx_label = QLabel("Schul-Kontext")
        ctx_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
        outer.addWidget(ctx_label)

        ctx_form = QFormLayout()
        ctx_form.setSpacing(8)

        # Klassenstufe combo (NULL + 5..13)
        self.grade_combo = QComboBox()
        self.grade_combo.addItem("—", None)
        for g in range(5, 14):
            self.grade_combo.addItem(f"Klasse {g}", g)
        if initial_grade is not None:
            idx = self.grade_combo.findData(initial_grade)
            if idx >= 0:
                self.grade_combo.setCurrentIndex(idx)
        ctx_form.addRow("Klassenstufe:", self.grade_combo)

        # School type combo (NULL + 3 predefined + Andere…)
        self.school_type_combo = QComboBox()
        self.school_type_combo.addItem("—", None)
        for st in SCHOOL_TYPES:
            self.school_type_combo.addItem(st, st)
        self.school_type_combo.addItem("Andere…", "__OTHER__")
        if initial_school_type:
            idx = self.school_type_combo.findData(initial_school_type)
            if idx >= 0:
                self.school_type_combo.setCurrentIndex(idx)
            else:
                last_idx = self.school_type_combo.count() - 1  # index of "Andere…"
                self.school_type_combo.insertItem(last_idx, initial_school_type, initial_school_type)
                self.school_type_combo.setCurrentIndex(last_idx)
        self.school_type_combo.activated.connect(self._on_school_type_activated)
        ctx_form.addRow("Schultyp:", self.school_type_combo)

        # Bundesland combo (NULL + 16 BL + Andere…)
        self.bundesland_combo = QComboBox()
        self.bundesland_combo.addItem("—", None)
        for bl in BUNDESLAENDER:
            self.bundesland_combo.addItem(bl, bl)
        self.bundesland_combo.addItem("Andere…", "__OTHER__")
        if initial_bundesland:
            idx = self.bundesland_combo.findData(initial_bundesland)
            if idx >= 0:
                self.bundesland_combo.setCurrentIndex(idx)
            else:
                last_idx = self.bundesland_combo.count() - 1
                self.bundesland_combo.insertItem(last_idx, initial_bundesland, initial_bundesland)
                self.bundesland_combo.setCurrentIndex(last_idx)
        self.bundesland_combo.activated.connect(self._on_bundesland_activated)
        ctx_form.addRow("Bundesland:", self.bundesland_combo)

        # School-Name (free text)
        self.school_name_edit = QLineEdit()
        self.school_name_edit.setPlaceholderText("z. B. Heinrich-Heine-Realschule")
        if initial_school_name:
            self.school_name_edit.setText(initial_school_name)
        ctx_form.addRow("Schul-Name:", self.school_name_edit)

        # School-Year (free text)
        self.school_year_edit = QLineEdit()
        self.school_year_edit.setPlaceholderText("2025/26")
        if initial_school_year:
            self.school_year_edit.setText(initial_school_year)
        ctx_form.addRow("Schuljahr:", self.school_year_edit)

        outer.addLayout(ctx_form)

        buttons = QHBoxLayout()
        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        ok = QPushButton("Speichern")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        outer.addLayout(buttons)

    def _on_birthday_edited(self, _qdate: QDate) -> None:
        self._birthday_set = True

    def _set_emoji(self, emoji: str) -> None:
        self._selected_avatar = emoji
        self._avatar_image = None
        for t in self._tiles:
            t.set_selected(t.emoji() == emoji)
        self._remove_btn.hide()
        self._refresh_preview()

    def _upload_photo(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Foto wählen", str(Path.home()),
            "Bilder (*.png *.jpg *.jpeg *.bmp *.gif)",
        )
        if not path_str:
            return
        pm = QPixmap(path_str)
        if pm.isNull():
            QMessageBox.warning(self, "Geht nicht", "Das Bild konnte nicht geladen werden.")
            return
        side = min(pm.width(), pm.height())
        x = (pm.width() - side) // 2
        y = (pm.height() - side) // 2
        pm = pm.copy(x, y, side, side)
        self._avatar_image = _pixmap_to_png_bytes(pm, max_dim=256)
        for t in self._tiles:
            t.set_selected(False)
        self._remove_btn.show()
        self._refresh_preview()

    def _remove_photo(self) -> None:
        self._avatar_image = None
        self._remove_btn.hide()
        for t in self._tiles:
            t.set_selected(t.emoji() == self._selected_avatar)
        self._refresh_preview()

    def _clear_birthday(self) -> None:
        self._birthday_set = False
        self.birthday_edit.blockSignals(True)
        self.birthday_edit.setDate(QDate(1900, 1, 1))
        self.birthday_edit.blockSignals(False)

    def _on_school_type_activated(self, idx: int) -> None:
        self._handle_other_trigger(self.school_type_combo, idx, "Schultyp eingeben", "Eigener Schultyp:")

    def _on_bundesland_activated(self, idx: int) -> None:
        self._handle_other_trigger(self.bundesland_combo, idx, "Bundesland eingeben", "Eigenes Bundesland:")

    def _handle_other_trigger(self, combo: QComboBox, idx: int, title: str, label: str) -> None:
        if combo.itemData(idx) != "__OTHER__":
            return
        text, ok = QInputDialog.getText(self, title, label)
        text = text.strip() if ok else ""
        if not text:
            combo.setCurrentIndex(0)  # revert to "—" (NULL)
            return
        last_idx = combo.count() - 1  # position of "Andere…"
        # Avoid duplicate insertion if user typed an existing predefined value
        existing = combo.findData(text)
        if existing >= 0:
            combo.setCurrentIndex(existing)
            return
        combo.insertItem(last_idx, text, text)
        combo.setCurrentIndex(last_idx)

    def _refresh_preview(self) -> None:
        self.preview.set_avatar(
            emoji=self._selected_avatar,
            image_bytes=self._avatar_image,
        )

    def values(self) -> ProfileValues:
        bd: str | None = None
        if self._birthday_set:
            d = self.birthday_edit.date()
            if d.year() > 1900:
                bd = d.toString("yyyy-MM-dd")
        briefing_text = self.style_edit.toPlainText().strip()
        return ProfileValues(
            name=self.name_edit.text().strip(),
            avatar=self._selected_avatar or "👤",
            avatar_image=self._avatar_image,
            birthday=bd,
            ai_style_briefing=briefing_text or None,
            grade=self.grade_combo.currentData(),
            school_type=self.school_type_combo.currentData() if self.school_type_combo.currentData() != "__OTHER__" else None,
            bundesland=self.bundesland_combo.currentData() if self.bundesland_combo.currentData() != "__OTHER__" else None,
            school_name=self.school_name_edit.text().strip() or None,
            school_year=self.school_year_edit.text().strip() or None,
        )


def _parse_iso_date(s: str | None) -> QDate | None:
    if not s:
        return None
    try:
        parts = s.split("-")
        if len(parts) == 3:
            return QDate(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, TypeError):
        pass
    return None


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
        add.setObjectName("primary")
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

        bottom = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.clicked.connect(self._back)
        bottom.addWidget(back)
        bottom.addStretch(1)
        outer.addLayout(bottom)

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
        dlg = _ProfileEditDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v.name:
            QMessageBox.information(self, "Name fehlt", "Bitte einen Namen vergeben.")
            return
        users_repo.create_user(
            self.conn, v.name, v.avatar,
            avatar_image=v.avatar_image, birthday=v.birthday,
        )
        self.reload()

    def _edit(self, user_id: int) -> None:
        u = users_repo.get_user(self.conn, user_id)
        if u is None:
            return
        dlg = _ProfileEditDialog(
            self,
            initial_name=u["name"],
            initial_avatar=u["avatar"],
            initial_image=row_get(u, "avatar_image"),
            initial_birthday=row_get(u, "birthday"),
            initial_style_briefing=row_get(u, "ai_style_briefing"),
            initial_grade=row_get(u, "grade"),
            initial_school_type=row_get(u, "school_type"),
            initial_bundesland=row_get(u, "bundesland"),
            initial_school_name=row_get(u, "school_name"),
            initial_school_year=row_get(u, "school_year"),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v.name:
            QMessageBox.information(self, "Name fehlt", "Bitte einen Namen vergeben.")
            return
        users_repo.update_user(
            self.conn, user_id,
            name=v.name, avatar=v.avatar,
            avatar_image=v.avatar_image, birthday=v.birthday,
            ai_style_briefing=v.ai_style_briefing,
            grade=v.grade, school_type=v.school_type,
            bundesland=v.bundesland, school_name=v.school_name,
            school_year=v.school_year,
        )
        self.reload()
        if self.window.active_user_id == user_id:
            self.window.user_changed.emit(user_id)

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
