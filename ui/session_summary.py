"""
session_summary.py - Modal Session Summary dialog shown on Stop.

Displays session statistics from CameraController.get_session_summary()
and provides navigation to the Reports page or the reports folder path.
No external applications are launched.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.theme import (
    ACCENT,
    BG_CARD,
    BG_DARK,
    BG_PANEL,
    BORDER,
    FONT_FAMILY,
    FONT_MONO,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


# ── Style helpers ─────────────────────────────────────────────────────────────

_BTN_BASE = f"""
    QPushButton {{
        border-radius: 8px;
        padding: 8px 22px;
        font-size: 13px;
        font-family: '{FONT_FAMILY}';
        font-weight: 600;
    }}
"""

_BTN_PRIMARY = _BTN_BASE + f"""
    QPushButton {{ background: #1db954; border: none; color: #fff; }}
    QPushButton:hover {{ background: #17a347; }}
"""

_BTN_SECONDARY = _BTN_BASE + f"""
    QPushButton {{
        background: #1e1e1e;
        border: 1px solid {BORDER};
        color: {TEXT_PRIMARY};
    }}
    QPushButton:hover {{
        background: #2a2a2a;
        border-color: {ACCENT};
        color: {ACCENT};
    }}
"""


def _lbl(text: str, size: int = 10, bold: bool = False,
         colour: str = TEXT_PRIMARY) -> QLabel:
    w = QFont.Weight.Bold if bold else QFont.Weight.Normal
    l = QLabel(text)
    l.setFont(QFont(FONT_FAMILY, size, w))
    l.setStyleSheet(f"color: {colour}; background: transparent;")
    return l


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background: {BORDER}; max-height: 1px;")
    return f


# ── Stat row ─────────────────────────────────────────────────────────────────

class _StatRow(QWidget):
    """One icon + label on the left, value on the right."""

    def __init__(self, icon: str, label: str, value: str, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        left = QHBoxLayout()
        left.setSpacing(8)
        icon_lbl = _lbl(icon, size=13, colour=ACCENT)
        icon_lbl.setFixedWidth(22)
        left.addWidget(icon_lbl)
        left.addWidget(_lbl(label, size=10, colour=TEXT_SECONDARY))
        layout.addLayout(left, stretch=1)

        val = QLabel(value)
        val.setFont(QFont(FONT_MONO, 11, QFont.Weight.Bold))
        val.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(val, stretch=1)


# ── Session Summary Dialog ────────────────────────────────────────────────────

class SessionSummaryDialog(QDialog):
    """
    Modal dialog shown automatically when a session is stopped.

    Accepts the dict returned by CameraController.get_session_summary().
    """

    # Signal-like: the caller checks this attribute after exec() to know
    # whether to navigate to the Reports page.
    open_reports_requested: bool = False

    def __init__(self, summary: dict, parent=None) -> None:
        super().__init__(parent)
        self.open_reports_requested = False

        self.setWindowTitle("Session Summary")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setStyleSheet(f"background: {BG_PANEL}; color: {TEXT_PRIMARY};")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        # ── Header ────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(_lbl("✅", size=20, colour=ACCENT))
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(_lbl("Session Complete", size=15, bold=True))
        title_col.addWidget(_lbl("Here is a summary of this tracking session.",
                                 size=9, colour=TEXT_SECONDARY))
        header.addLayout(title_col)
        header.addStretch()
        root.addLayout(header)
        root.addWidget(_divider())

        # ── Stats card ────────────────────────────────────────────────────────
        card = QWidget()
        card.setStyleSheet(
            f"background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 10px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(2)

        runtime  = summary.get("runtime_s", 0.0)
        mins, secs = divmod(int(runtime), 60)
        duration_str = f"{mins:02d}:{secs:02d}  ({runtime:.1f} s)"

        rows = [
            # Section: Timing
            ("⏱️",  "Session Duration",   duration_str),
            ("⚡",  "Average FPS",        f"{summary.get('avg_fps', 0.0):.1f}"),
            ("🔝",  "Maximum FPS",        f"{summary.get('max_fps', 0.0):.1f}"),
            ("📈",  "Final FPS",          f"{summary.get('current_fps', 0.0):.1f}"),
            None,   # divider
            # Section: Detections
            ("🎯",  "Total Detections",   str(summary.get("detection_count", 0))),
            ("🔖",  "Tracks Created",     str(summary.get("tracks_created", 0))),
            ("❌",  "Lost Tracks",        str(summary.get("lost_tracks", 0))),
            None,
            # Section: Speed
            ("💨",  "Average Speed",      f"{summary.get('avg_speed', 0.0):.1f} px/s"),
            ("🚀",  "Maximum Speed",      f"{summary.get('max_speed', 0.0):.1f} px/s"),
            None,
            # Section: Reports
            ("📄",  "JSON Report",
             self._short_path(summary.get("json_report_path", "—"))),
            ("📝",  "TXT Report",
             self._short_path(summary.get("txt_report_path", "—"))),
        ]

        for row in rows:
            if row is None:
                card_layout.addWidget(_divider())
            else:
                card_layout.addWidget(_StatRow(*row, parent=card))

        root.addWidget(card)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(_BTN_SECONDARY)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)

        btn_reports = QPushButton("📄  Open Reports Page")
        btn_reports.setStyleSheet(_BTN_PRIMARY)
        btn_reports.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reports.clicked.connect(self._on_open_reports)

        btn_folder = QPushButton("📂  Reports Folder")
        btn_folder.setStyleSheet(_BTN_SECONDARY)
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_folder.clicked.connect(self._on_open_folder)

        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        btn_row.addWidget(btn_folder)
        btn_row.addWidget(btn_reports)
        root.addLayout(btn_row)

        self._summary = summary

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_open_reports(self) -> None:
        self.open_reports_requested = True
        self.accept()

    def _on_open_folder(self) -> None:
        """Show the reports folder path in a label — no external app launched."""
        from PySide6.QtWidgets import QMessageBox
        path = os.path.abspath(os.path.join("outputs", "reports"))
        os.makedirs(path, exist_ok=True)
        QMessageBox.information(
            self,
            "Reports Folder",
            f"Reports are stored in:\n{path}",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _short_path(path: str) -> str:
        """Show only the last two path components to keep the dialog compact."""
        if path == "—":
            return "—"
        parts = path.replace("\\", "/").split("/")
        return "/".join(parts[-2:]) if len(parts) >= 2 else path
