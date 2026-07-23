"""
widgets.py - Reusable UI components for the Ball Detection & Tracking System.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme import (
    ACCENT,
    BG_CARD,
    FONT_FAMILY,
    FONT_MONO,
    RED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    YELLOW,
)


# ── Stat Card ─────────────────────────────────────────────────────────────────

class StatCard(QWidget):
    """A rounded dark card showing an icon, label, and live value."""

    def __init__(self, icon: str, label: str, value: str = "—", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setMinimumHeight(80)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(4)

        # Header row: icon + label
        header = QHBoxLayout()
        header.setSpacing(6)

        icon_lbl = QLabel(icon)
        icon_lbl.setFont(QFont(FONT_FAMILY, 14))
        icon_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent;")
        icon_lbl.setFixedWidth(22)

        name_lbl = QLabel(label)
        name_lbl.setFont(QFont(FONT_FAMILY, 10))
        name_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")

        header.addWidget(icon_lbl)
        header.addWidget(name_lbl)
        header.addStretch()

        # Value
        self._value_lbl = QLabel(value)
        self._value_lbl.setFont(QFont(FONT_MONO, 18, QFont.Weight.Bold))
        self._value_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        root.addLayout(header)
        root.addWidget(self._value_lbl)

    def set_value(self, value: str) -> None:
        """Update the displayed value."""
        self._value_lbl.setText(value)


# ── Mode Badge ────────────────────────────────────────────────────────────────

class ModeBadge(QWidget):
    """Pill-shaped badge showing the current detection mode with a colour dot."""

    _COLOURS = {
        "TRACKING":  ACCENT,
        "SEARCHING": YELLOW,
        "STOPPED":   RED,
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 14, 4)
        layout.setSpacing(7)

        self._dot = QLabel("●")
        self._dot.setFont(QFont(FONT_FAMILY, 10))

        self._label = QLabel("STOPPED")
        self._label.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.Medium))
        self._label.setStyleSheet("background: transparent;")

        layout.addWidget(self._dot)
        layout.addWidget(self._label)

        self.setStyleSheet(
            "background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 14px;"
        )
        self.set_mode("STOPPED")

    def set_mode(self, mode: str) -> None:
        """Update the badge text and colour. mode must be TRACKING/SEARCHING/STOPPED."""
        colour = self._COLOURS.get(mode, RED)
        self._dot.setStyleSheet(f"color: {colour}; background: transparent;")
        self._label.setText(mode)
        self._label.setStyleSheet(f"color: {colour}; background: transparent;")


# ── Horizontal Divider ────────────────────────────────────────────────────────

class HDivider(QFrame):
    """A thin 1 px horizontal rule."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("divider")
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)


# ── Nav Button ────────────────────────────────────────────────────────────────

class NavButton(QPushButton):
    """Sidebar navigation button with an emoji icon and text label."""

    def __init__(self, icon: str, label: str, parent=None) -> None:
        super().__init__(f"  {icon}   {label}", parent)
        self.setObjectName("navBtn")
        self.setCheckable(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
