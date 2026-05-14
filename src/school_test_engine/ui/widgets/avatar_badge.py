from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QPainter, QPainterPath, QPixmap, QPixmapCache
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QWidget

from ..design import Semantic


PLACEHOLDER_SVG_PATH = (
    Path(__file__).resolve().parents[3].parent / "assets" / "avatar-placeholder.svg"
)


class AvatarBadge(QLabel):
    """Rundes Avatar — Foto wenn vorhanden, sonst SVG-Silhouette.

    Bytes werden über QPixmapCache gecacht (Schlüssel = sha1+Durchmesser),
    damit derselbe Avatar an mehreren Stellen (Chip, Liste, Picker) nicht
    bei jedem Rerender neu dekodiert wird. Der SVG-Placeholder wird ebenfalls
    pro Durchmesser einmal in den Cache gerendert.
    """

    def __init__(
        self,
        *,
        emoji: str,
        image_bytes: bytes | None = None,
        diameter: int = 56,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background: transparent; "
            f"border: 1px solid {Semantic.BORDER}; "
            f"border-radius: {diameter // 2}px;"
        )
        self.set_avatar(emoji=emoji, image_bytes=image_bytes)

    def set_avatar(self, *, emoji: str, image_bytes: bytes | None) -> None:
        # Phase 13: emoji parameter retained for backward compat but ignored.
        if image_bytes:
            pm = _cached_round_pixmap(image_bytes, self._diameter - 4)
            if pm is not None:
                self.setPixmap(pm)
                self.setText("")
                return
        self._render_placeholder()

    def _render_placeholder(self) -> None:
        self.clear()
        pm = _cached_placeholder_pixmap(self._diameter)
        self.setPixmap(pm)
        self.setStyleSheet(
            f"background: transparent; border-radius: {self._diameter // 2}px;"
        )


def round_pixmap(pm: QPixmap, diameter: int) -> QPixmap:
    target = QPixmap(diameter, diameter)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addEllipse(0, 0, diameter, diameter)
    painter.setClipPath(path)
    src = pm.scaled(
        diameter, diameter,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = (diameter - src.width()) // 2
    y = (diameter - src.height()) // 2
    painter.drawPixmap(QRect(x, y, src.width(), src.height()), src)
    painter.end()
    return target


def _cached_round_pixmap(image_bytes: bytes, diameter: int) -> QPixmap | None:
    digest = hashlib.sha1(image_bytes).hexdigest()[:16]
    key = f"avatar:{digest}:{diameter}"
    cached = QPixmapCache.find(key)
    if cached is not None:
        return cached
    pm = QPixmap()
    if not pm.loadFromData(image_bytes):
        return None
    rounded = round_pixmap(pm, diameter)
    QPixmapCache.insert(key, rounded)
    return rounded


def _cached_placeholder_pixmap(diameter: int) -> QPixmap:
    key = f"avatar-placeholder:{diameter}"
    cached = QPixmapCache.find(key)
    if cached is not None:
        return cached
    pm = QPixmap(diameter, diameter)
    pm.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(str(PLACEHOLDER_SVG_PATH))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    QPixmapCache.insert(key, pm)
    return pm
