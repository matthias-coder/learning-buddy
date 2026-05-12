from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout

from ..design import FontFamily
from .avatar_badge import round_pixmap
from .shadow import apply_warm_shadow


class ProfileCard(QFrame):
    """Klickbare Karte für die Profilauswahl. Großes Avatar (Emoji oder Foto) + Name."""

    clicked = Signal()

    def __init__(
        self,
        *,
        avatar: str,
        name: str,
        meta: str | None = None,
        plus: bool = False,
        image_bytes: bytes | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("profileCardPlus" if plus else "profileCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(240, 210)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        if not plus:
            apply_warm_shadow(self, blur=14, dy=2, alpha=0.07)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 22, 20, 20)
        layout.setSpacing(8)

        avatar_lbl = QLabel()
        avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_lbl.setFixedHeight(90)
        if image_bytes:
            pm = QPixmap()
            if pm.loadFromData(image_bytes):
                avatar_lbl.setPixmap(round_pixmap(pm, 84))
        if not avatar_lbl.pixmap():
            avatar_lbl.setText(avatar)
            big = QFont(); big.setPointSize(48); avatar_lbl.setFont(big)
        layout.addWidget(avatar_lbl)

        name_lbl = QLabel(name)
        name_lbl.setObjectName("profileCardName")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setFont(QFont(FontFamily.DISPLAY, 16, QFont.Weight.Medium))
        layout.addWidget(name_lbl)

        if meta:
            meta_lbl = QLabel(meta)
            meta_lbl.setObjectName("profileCardMeta")
            meta_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            meta_lbl.setFont(QFont(FontFamily.MONO, 9))
            layout.addWidget(meta_lbl)

        layout.addStretch(1)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self.setProperty("hover", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setProperty("hover", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)
