from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QDate, QIODevice, Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
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
from .._layouts import row_get
from ..design import Color, FontFamily, Semantic
from ..widgets.avatar_badge import AvatarBadge


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


class ProfileEditPage(QWidget):
    """Inline page for creating or editing a user profile. Replaces the old
    _ProfileEditDialog from Phase 6+."""

    def __init__(self, window, conn: sqlite3.Connection):
        super().__init__()
        self.window = window
        self.conn = conn
        self._user_id: int | None = None
        self._return_to: str = "picker"
        self._avatar_image: bytes | None = None
        self._birthday_set: bool = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(14)

        # Header
        head = QHBoxLayout()
        back = QPushButton("← Zurück")
        back.setObjectName("text")
        back.clicked.connect(self._cancel)
        head.addWidget(back)
        head.addStretch(1)
        self.save_btn = QPushButton("Speichern")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save)
        head.addWidget(self.save_btn)
        layout.addLayout(head)

        eyebrow = QLabel("PROFIL")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)

        self.title_label = QLabel("Neues Profil")
        self.title_label.setFont(QFont(FontFamily.DISPLAY, 28, QFont.Weight.Normal))
        layout.addWidget(self.title_label)

        # Avatar block
        avatar_row = QHBoxLayout()
        avatar_row.setSpacing(16)
        self.avatar_preview = AvatarBadge(emoji="👤", image_bytes=None, diameter=96)
        avatar_row.addWidget(self.avatar_preview)
        avatar_buttons = QVBoxLayout()
        upload = QPushButton("Foto auswählen…")
        upload.setObjectName("text")
        upload.clicked.connect(self._upload_photo)
        avatar_buttons.addWidget(upload)
        self.remove_photo_btn = QPushButton("Foto entfernen")
        self.remove_photo_btn.setObjectName("text")
        self.remove_photo_btn.clicked.connect(self._remove_photo)
        self.remove_photo_btn.setVisible(False)
        avatar_buttons.addWidget(self.remove_photo_btn)
        avatar_buttons.addStretch(1)
        avatar_row.addLayout(avatar_buttons, 1)
        layout.addLayout(avatar_row)

        # Form
        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("z. B. Clemens")
        form.addRow("Name:", self.name_edit)

        self.birthday_edit = QDateEdit()
        self.birthday_edit.setCalendarPopup(True)
        self.birthday_edit.setDisplayFormat("dd.MM.yyyy")
        self.birthday_edit.setDate(QDate(1900, 1, 1))
        clear_bd = QPushButton("löschen")
        clear_bd.setObjectName("text")
        clear_bd.clicked.connect(self._clear_birthday)
        bd_row = QHBoxLayout()
        bd_row.addWidget(self.birthday_edit, 1)
        bd_row.addWidget(clear_bd)
        form.addRow("Geburtstag:", bd_row)

        layout.addLayout(form)

        # Style-Briefing (Phase 8)
        style_label = QLabel("KI-Stil-Hinweis (optional)")
        style_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
        layout.addWidget(style_label)
        self.style_edit = QPlainTextEdit()
        self.style_edit.setPlaceholderText(
            "z. B.: Schreibstil: Du-Form, freundlich.\n"
            "Mathe: saubere Äquivalenzumformungen in der Erklärung."
        )
        self.style_edit.setMaximumHeight(110)
        layout.addWidget(self.style_edit)

        # Schul-Kontext (Phase 9)
        ctx_label = QLabel("Schul-Kontext")
        ctx_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
        layout.addWidget(ctx_label)

        ctx_form = QFormLayout()
        ctx_form.setSpacing(8)

        self.grade_combo = QComboBox()
        self.grade_combo.addItem("—", None)
        for g in range(5, 14):
            self.grade_combo.addItem(f"Klasse {g}", g)
        ctx_form.addRow("Klassenstufe:", self.grade_combo)

        self.school_type_combo = QComboBox()
        self.school_type_combo.addItem("—", None)
        for st in SCHOOL_TYPES:
            self.school_type_combo.addItem(st, st)
        self.school_type_combo.addItem("Andere…", "__OTHER__")
        self.school_type_combo.activated.connect(self._on_school_type_activated)
        ctx_form.addRow("Schultyp:", self.school_type_combo)

        self.bundesland_combo = QComboBox()
        self.bundesland_combo.addItem("—", None)
        for bl in BUNDESLAENDER:
            self.bundesland_combo.addItem(bl, bl)
        self.bundesland_combo.addItem("Andere…", "__OTHER__")
        self.bundesland_combo.activated.connect(self._on_bundesland_activated)
        ctx_form.addRow("Bundesland:", self.bundesland_combo)

        self.school_name_edit = QLineEdit()
        self.school_name_edit.setPlaceholderText("z. B. Heinrich-Heine-Realschule")
        ctx_form.addRow("Schul-Name:", self.school_name_edit)

        self.school_year_edit = QLineEdit()
        self.school_year_edit.setPlaceholderText("2025/26")
        ctx_form.addRow("Schuljahr:", self.school_year_edit)

        layout.addLayout(ctx_form)

        # Schulkalender (Phase 15)
        ical_label = QLabel("Schulkalender")
        ical_label.setStyleSheet("color: #4a4538; font-weight: 500; padding-top: 8px;")
        layout.addWidget(ical_label)

        self.ical_feed_url_edit = QPlainTextEdit()
        self.ical_feed_url_edit.setPlaceholderText(
            "https://start.schulportal.hessen.de/kalender.php?..."
        )
        self.ical_feed_url_edit.setMaximumHeight(80)
        layout.addWidget(self.ical_feed_url_edit)

        ical_hint = QLabel("Findest du im Schulportal unter „Kalender → Export → iCal\".")
        ical_hint.setStyleSheet("color: #b3a98e; font-size: 9pt;")
        ical_hint.setWordWrap(True)
        layout.addWidget(ical_hint)

        # Footer: Delete (visible only in edit mode)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.delete_btn = QPushButton("Löschen")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._delete)
        self.delete_btn.setVisible(False)
        footer.addWidget(self.delete_btn)
        layout.addLayout(footer)

        layout.addStretch(1)

    def show_for(self, user_id: int | None = None, return_to: str = "picker") -> None:
        self._user_id = user_id
        self._return_to = return_to
        self._reset_fields()
        if user_id is None:
            self.title_label.setText("Neues Profil")
            self.delete_btn.setVisible(False)
        else:
            self.title_label.setText("Profil bearbeiten")
            self.delete_btn.setVisible(True)
            self._load_user(user_id)

    def _reset_fields(self) -> None:
        self.name_edit.setText("")
        self._avatar_image = None
        self.avatar_preview.set_avatar(emoji="👤", image_bytes=None)
        self.remove_photo_btn.setVisible(False)
        self._birthday_set = False
        self.birthday_edit.setDate(QDate(1900, 1, 1))
        self.style_edit.setPlainText("")
        self.grade_combo.setCurrentIndex(0)
        self.school_type_combo.setCurrentIndex(0)
        self.bundesland_combo.setCurrentIndex(0)
        self.school_name_edit.setText("")
        self.school_year_edit.setText("")
        self.ical_feed_url_edit.setPlainText("")

    def _load_user(self, user_id: int) -> None:
        u = users_repo.get_user(self.conn, user_id)
        if u is None:
            return
        self.name_edit.setText(u["name"] or "")
        self._avatar_image = row_get(u, "avatar_image")
        self.avatar_preview.set_avatar(emoji="👤", image_bytes=self._avatar_image)
        self.remove_photo_btn.setVisible(self._avatar_image is not None)
        bd = row_get(u, "birthday")
        if bd:
            try:
                d = datetime.fromisoformat(bd).date()
                self.birthday_edit.setDate(QDate(d.year, d.month, d.day))
                self._birthday_set = True
            except ValueError:
                pass
        briefing = row_get(u, "ai_style_briefing")
        if briefing:
            self.style_edit.setPlainText(briefing)
        grade = row_get(u, "grade")
        if grade is not None:
            idx = self.grade_combo.findData(int(grade))
            if idx >= 0:
                self.grade_combo.setCurrentIndex(idx)
        st = row_get(u, "school_type")
        if st:
            idx = self.school_type_combo.findData(st)
            if idx >= 0:
                self.school_type_combo.setCurrentIndex(idx)
            else:
                last_idx = self.school_type_combo.count() - 1
                self.school_type_combo.insertItem(last_idx, st, st)
                self.school_type_combo.setCurrentIndex(last_idx)
        bl = row_get(u, "bundesland")
        if bl:
            idx = self.bundesland_combo.findData(bl)
            if idx >= 0:
                self.bundesland_combo.setCurrentIndex(idx)
            else:
                last_idx = self.bundesland_combo.count() - 1
                self.bundesland_combo.insertItem(last_idx, bl, bl)
                self.bundesland_combo.setCurrentIndex(last_idx)
        sn = row_get(u, "school_name")
        if sn:
            self.school_name_edit.setText(sn)
        sy = row_get(u, "school_year")
        if sy:
            self.school_year_edit.setText(sy)
        self.ical_feed_url_edit.setPlainText(row_get(u, "ical_feed_url") or "")

    def _upload_photo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Foto auswählen", "", "Bilder (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        pm = QPixmap(path)
        if pm.isNull():
            QMessageBox.warning(self, "Fehler", "Bild konnte nicht geladen werden.")
            return
        self._avatar_image = _pixmap_to_png_bytes(pm)
        self.avatar_preview.set_avatar(emoji="👤", image_bytes=self._avatar_image)
        self.remove_photo_btn.setVisible(True)

    def _remove_photo(self) -> None:
        self._avatar_image = None
        self.avatar_preview.set_avatar(emoji="👤", image_bytes=None)
        self.remove_photo_btn.setVisible(False)

    def _clear_birthday(self) -> None:
        self._birthday_set = False
        self.birthday_edit.blockSignals(True)
        self.birthday_edit.setDate(QDate(1900, 1, 1))
        self.birthday_edit.blockSignals(False)

    def _on_school_type_activated(self, idx: int) -> None:
        self._handle_other_trigger(
            self.school_type_combo, idx, "Schultyp eingeben", "Eigener Schultyp:"
        )

    def _on_bundesland_activated(self, idx: int) -> None:
        self._handle_other_trigger(
            self.bundesland_combo, idx, "Bundesland eingeben", "Eigenes Bundesland:"
        )

    def _handle_other_trigger(self, combo: QComboBox, idx: int, title: str, label: str) -> None:
        if combo.itemData(idx) != "__OTHER__":
            return
        text, ok = QInputDialog.getText(self, title, label)
        text = text.strip() if ok else ""
        if not text:
            combo.setCurrentIndex(0)
            return
        last_idx = combo.count() - 1
        existing = combo.findData(text)
        if existing >= 0:
            combo.setCurrentIndex(existing)
            return
        combo.insertItem(last_idx, text, text)
        combo.setCurrentIndex(last_idx)

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Name fehlt", "Bitte einen Namen vergeben.")
            return

        birthday = None
        if self._birthday_set:
            d = self.birthday_edit.date()
            if d.year() > 1900:
                birthday = d.toString("yyyy-MM-dd")

        style_text = self.style_edit.toPlainText().strip() or None
        grade_val = self.grade_combo.currentData()
        school_type_val = self.school_type_combo.currentData()
        if school_type_val == "__OTHER__":
            school_type_val = None
        bundesland_val = self.bundesland_combo.currentData()
        if bundesland_val == "__OTHER__":
            bundesland_val = None
        school_name_val = self.school_name_edit.text().strip() or None
        school_year_val = self.school_year_edit.text().strip() or None
        raw_url = self.ical_feed_url_edit.toPlainText().strip()
        if raw_url and not raw_url.startswith("https://"):
            QMessageBox.warning(
                self, "Ungültige URL",
                "Die Feed-URL muss mit „https://\" beginnen oder leer bleiben.",
            )
            return
        ical_feed_url_val = raw_url if raw_url else None

        if self._user_id is None:
            new_uid = users_repo.create_user(
                self.conn, name, "👤",
                avatar_image=self._avatar_image,
                birthday=birthday,
            )
            users_repo.update_user(
                self.conn, new_uid,
                ai_style_briefing=style_text,
                grade=grade_val,
                school_type=school_type_val,
                bundesland=bundesland_val,
                school_name=school_name_val,
                school_year=school_year_val,
                ical_feed_url=ical_feed_url_val,
            )
        else:
            users_repo.update_user(
                self.conn, self._user_id,
                name=name,
                avatar_image=self._avatar_image,
                birthday=birthday,
                ai_style_briefing=style_text,
                grade=grade_val,
                school_type=school_type_val,
                bundesland=bundesland_val,
                school_name=school_name_val,
                school_year=school_year_val,
                ical_feed_url=ical_feed_url_val,
            )
            if self.window.active_user_id == self._user_id and hasattr(self.window, "user_changed"):
                self.window.user_changed.emit(self._user_id)

        self._navigate_back()

    def _cancel(self) -> None:
        self._navigate_back()

    def _delete(self) -> None:
        if self._user_id is None:
            return
        if self.window.active_user_id == self._user_id:
            QMessageBox.information(
                self, "Aktives Profil",
                "Du kannst das aktive Profil nicht löschen. Wechsle zuerst.",
            )
            return
        reply = QMessageBox.question(
            self, "Profil löschen?",
            f"Profil und alle zugehörigen Daten endgültig löschen?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        users_repo.delete_user(self.conn, self._user_id)
        self._navigate_back()

    def _navigate_back(self) -> None:
        target = self._return_to
        if target == "manager":
            self.window.show_profile_manager("manager")
        elif target == "menu":
            self.window.show_menu()
        else:
            self.window.show_profile_picker()
