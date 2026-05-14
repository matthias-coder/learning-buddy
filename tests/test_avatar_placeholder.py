"""Phase 13: AvatarBadge and ProfileCard render the SVG placeholder
instead of OS-color-emoji when no image is set."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from school_test_engine.ui.widgets.avatar_badge import AvatarBadge
from school_test_engine.ui.widgets.profile_card import ProfileCard


def _ensure_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_avatar_badge_placeholder_renders_pixmap_not_text():
    _ensure_app()
    badge = AvatarBadge(emoji="ignored", image_bytes=None, diameter=64)
    # Phase 13: placeholder is rendered as pixmap from SVG, not text
    assert badge.text() == ""
    pm = badge.pixmap()
    assert pm is not None and not pm.isNull(), "AvatarBadge placeholder must be a pixmap"


def test_avatar_badge_with_image_still_works():
    _ensure_app()
    # 1x1 transparent PNG
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63000100000005000100"
        "0d0a2db40000000049454e44ae426082"
    )
    badge = AvatarBadge(emoji="ignored", image_bytes=png_bytes, diameter=64)
    assert badge.text() == ""
    pm = badge.pixmap()
    assert pm is not None and not pm.isNull()


def test_profile_card_placeholder_renders_pixmap_not_text():
    _ensure_app()
    card = ProfileCard(avatar="ignored", name="Test", meta=None, image_bytes=None)
    # Walk children to find the avatar QLabel — first QLabel with fixed height 90
    from PySide6.QtWidgets import QLabel
    avatar_lbl = None
    for child in card.findChildren(QLabel):
        if child.height() == 90 or child.minimumHeight() == 90 or child.maximumHeight() == 90:
            avatar_lbl = child
            break
        # Fallback: first QLabel with no objectName starting with "profileCard"
        if not child.objectName().startswith("profileCard"):
            avatar_lbl = child
            break
    assert avatar_lbl is not None, "could not find avatar label in ProfileCard"
    assert avatar_lbl.text() == "", "Phase 13: avatar label must not render emoji text"
    pm = avatar_lbl.pixmap()
    assert pm is not None and not pm.isNull(), "ProfileCard placeholder must be a pixmap"
