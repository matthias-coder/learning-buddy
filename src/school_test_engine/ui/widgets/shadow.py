from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget


def apply_warm_shadow(
    widget: QWidget,
    *,
    blur: int = 16,
    dy: int = 3,
    alpha: float = 0.08,
) -> QGraphicsDropShadowEffect:
    """Wende einen warmen Schatten an (rgba 58,29,16 mit alpha).

    Default: shadow-md aus dem Kessler-System (für Hero-Cards).
    Für sanftere Karten: blur=10, dy=2, alpha=0.06.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setColor(QColor(58, 29, 16, int(alpha * 255)))
    effect.setOffset(0, dy)
    widget.setGraphicsEffect(effect)
    return effect
