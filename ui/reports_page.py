"""
reports_page.py - In-app Reports browser for the Ball Detection & Tracking System.

Reads JSON and TXT reports from outputs/reports/, displays a searchable list,
and renders contents inside the application without launching external viewers.
"""

import json
import os
import shutil
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
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

_REPORTS_DIR = os.path.join("outputs", "reports")

# ── Shared style helpers ──────────────────────────────────────────────────────

_BTN_STYLE = f"""
    QPushButton {{
        background: #1e1e1e;
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 5px 14px;
        font-size: 12px;
        color: {TEXT_PRIMARY};
        font-family: '{FONT_FAMILY}';
    }}
    QPushButton:hover {{
        background: #2a2a2a;
        border-color: {ACCENT};
        color: {ACCENT};
    }}
    QPushButton:disabled {{
        color: #444;
        border-color: #333;
    }}
"""

_SEARCH_STYLE = f"""
    QLineEdit {{
        background: #1a1a1a;
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 5px 10px;
        color: {TEXT_PRIMARY};
        font-size: 12px;
        font-family: '{FONT_FAMILY}';
    }}
    QLineEdit:focus {{ border-color: {ACCENT}; }}
"""

_LIST_STYLE = f"""
    QListWidget {{
        background: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 6px;
        color: {TEXT_PRIMARY};
        font-size: 12px;
        font-family: '{FONT_FAMILY}';
        outline: none;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-bottom: 1px solid #222;
    }}
    QListWidget::item:selected {{
        background: #1e2e1e;
        color: {ACCENT};
        border-left: 3px solid {ACCENT};
    }}
    QListWidget::item:hover:!selected {{
        background: #1e1e1e;
    }}
"""

_VIEWER_STYLE = f"""
    QTextEdit {{
        background: {BG_DARK};
        border: 1px solid {BORDER};
        border-radius: 6px;
        color: {TEXT_PRIMARY};
        font-family: '{FONT_MONO}';
        font-size: 12px;
        padding: 8px;
    }}
"""


def _lbl(text: str, size: int = 10, bold: bool = False,
         colour: str = TEXT_PRIMARY) -> QLabel:
    w = QFont.Weight.Bold if bold else QFont.Weight.Normal
    l = QLabel(text)
    l.setFont(QFont(FONT_FAMILY, size, w))
    l.setStyleSheet(f"color: {colour}; background: transparent;")
    return l


# ── JSON stats card ───────────────────────────────────────────────────────────

class _StatCard(QWidget):
    """Small inline card showing one key stat from a JSON report."""

    def __init__(self, icon: str, label: str, value: str, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"background: #1e1e1e; border: 1px solid {BORDER}; border-radius: 8px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(6)
        icon_lbl = _lbl(icon, size=13, colour=ACCENT)
        icon_lbl.setFixedWidth(20)
        top.addWidget(icon_lbl)
        top.addWidget(_lbl(label, size=9, colour=TEXT_SECONDARY))
        top.addStretch()
        layout.addLayout(top)

        val_lbl = QLabel(value)
        val_lbl.setFont(QFont(FONT_MONO, 13, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(val_lbl)


# ── Reports Page ──────────────────────────────────────────────────────────────

class ReportsPage(QWidget):
    """
    Full in-app reports browser.

    Left panel  — searchable file list + toolbar (Refresh / Delete / Open folder).
    Right panel — report viewer (stat cards + pretty content for JSON; plain for TXT).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PANEL};")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._current_path: Optional[str] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # Title row
        title_row = QHBoxLayout()
        title_row.addWidget(_lbl("Reports", size=16, bold=True))
        title_row.addStretch()
        root.addLayout(title_row)
        root.addWidget(_lbl("Browse and inspect saved session reports.",
                            size=9, colour=TEXT_SECONDARY))
        root.addSpacing(4)

        # Splitter: list | viewer
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; width: 1px; }}")
        splitter.setChildrenCollapsible(False)

        # ── Left: file list ───────────────────────────────────────────────────
        left = QWidget()
        left.setStyleSheet(f"background: {BG_PANEL};")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Filter reports…")
        self._search.setStyleSheet(_SEARCH_STYLE)
        self._search.textChanged.connect(self._filter_list)
        left_layout.addWidget(self._search)

        # File list
        self._list = QListWidget()
        self._list.setStyleSheet(_LIST_STYLE)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._list, stretch=1)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self._btn_refresh = QPushButton("↻  Refresh")
        self._btn_refresh.setStyleSheet(_BTN_STYLE)
        self._btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh.clicked.connect(self.refresh)

        self._btn_delete = QPushButton("🗑  Delete")
        self._btn_delete.setStyleSheet(_BTN_STYLE)
        self._btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._delete_selected)

        self._btn_folder = QPushButton("📂  Open Folder")
        self._btn_folder.setStyleSheet(_BTN_STYLE)
        self._btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_folder.clicked.connect(self._open_folder)

        toolbar.addWidget(self._btn_refresh)
        toolbar.addWidget(self._btn_delete)
        toolbar.addWidget(self._btn_folder)
        toolbar.addStretch()
        left_layout.addLayout(toolbar)

        left.setMinimumWidth(200)
        left.setMaximumWidth(320)
        splitter.addWidget(left)

        # ── Right: viewer ─────────────────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet(f"background: {BG_PANEL};")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        # Stat cards row (JSON only, hidden for TXT)
        self._cards_row = QWidget()
        self._cards_row.setStyleSheet("background: transparent;")
        self._cards_layout = QHBoxLayout(self._cards_row)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_row.setVisible(False)
        right_layout.addWidget(self._cards_row)

        # File name label
        self._file_label = _lbl("No report selected", size=11, bold=True)
        right_layout.addWidget(self._file_label)

        # Text viewer
        self._viewer = QTextEdit()
        self._viewer.setReadOnly(True)
        self._viewer.setStyleSheet(_VIEWER_STYLE)
        self._viewer.setPlaceholderText("Select a report from the list on the left.")
        right_layout.addWidget(self._viewer, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, stretch=1)

        # Initial load
        self.refresh()

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Re-scan outputs/reports/ and rebuild the file list."""
        current_text = (
            self._list.currentItem().text()
            if self._list.currentItem() else None
        )
        self._list.clear()

        if not os.path.isdir(_REPORTS_DIR):
            return

        files = sorted(
            (f for f in os.listdir(_REPORTS_DIR)
             if f.endswith(".json") or f.endswith(".txt")),
            reverse=True,          # newest first (alphabetical desc works for timestamps)
        )
        for fname in files:
            item = QListWidgetItem(fname)
            item.setData(Qt.ItemDataRole.UserRole,
                         os.path.join(_REPORTS_DIR, fname))
            self._list.addItem(item)

        # Re-select the previously selected file if it still exists
        if current_text:
            matches = self._list.findItems(current_text, Qt.MatchFlag.MatchExactly)
            if matches:
                self._list.setCurrentItem(matches[0])

        self._filter_list(self._search.text())

    # ── Internal slots ────────────────────────────────────────────────────────

    def _filter_list(self, query: str) -> None:
        """Show only list items whose name contains the search query."""
        q = query.strip().lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(bool(q and q not in item.text().lower()))

    def _on_selection_changed(self, current: QListWidgetItem, _prev) -> None:
        if current is None:
            self._btn_delete.setEnabled(False)
            return

        self._btn_delete.setEnabled(True)
        path: str = current.data(Qt.ItemDataRole.UserRole)
        self._current_path = path
        self._load_report(path)

    def _load_report(self, path: str) -> None:
        """Read the file and populate the viewer + stat cards."""
        fname = os.path.basename(path)
        self._file_label.setText(fname)
        self._clear_cards()

        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as e:
            self._viewer.setPlainText(f"Could not read file:\n{e}")
            return

        if path.endswith(".json"):
            self._render_json(raw)
        else:
            self._render_txt(raw)

    def _render_json(self, raw: str) -> None:
        """Pretty-print JSON and show key stat cards."""
        try:
            data: dict = json.loads(raw)
        except json.JSONDecodeError as e:
            self._viewer.setPlainText(f"Invalid JSON:\n{e}\n\n{raw}")
            return

        # Stat cards
        _CARD_DEFS = [
            ("⏱️", "Runtime",       data.get("total_runtime_s",    0), "{:.1f} s"),
            ("⚡", "Avg FPS",       data.get("avg_fps",            0), "{:.1f}"),
            ("🔝", "Max FPS",       data.get("max_fps",            0), "{:.1f}"),
            ("💨", "Avg Speed",     data.get("avg_ball_speed_px_s",0), "{:.1f} px/s"),
            ("🎯", "Detections",    data.get("frames_processed",   0), "{}"),
            ("🔖", "Tracks Created",data.get("tracks_created",     0), "{}"),
        ]
        for icon, label, value, fmt in _CARD_DEFS:
            try:
                val_str = fmt.format(value)
            except (TypeError, ValueError):
                val_str = str(value)
            card = _StatCard(icon, label, val_str, self._cards_row)
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch()
        self._cards_row.setVisible(True)

        # Pretty-print
        pretty = json.dumps(data, indent=2)
        self._viewer.setPlainText(pretty)

    def _render_txt(self, raw: str) -> None:
        """Display plain-text report as-is."""
        self._cards_row.setVisible(False)
        self._viewer.setPlainText(raw)

    def _clear_cards(self) -> None:
        """Remove all stat cards from the cards row."""
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards_row.setVisible(False)

    def _delete_selected(self) -> None:
        """Confirm and delete the currently selected report file."""
        if not self._current_path or not os.path.isfile(self._current_path):
            return

        fname = os.path.basename(self._current_path)
        box = QMessageBox(self)
        box.setWindowTitle("Delete Report")
        box.setText(f"Delete  {fname}?")
        box.setInformativeText("This cannot be undone.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.setIcon(QMessageBox.Icon.Warning)

        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        try:
            os.remove(self._current_path)
        except OSError as e:
            QMessageBox.warning(self, "Delete Failed", str(e))
            return

        self._current_path = None
        self._viewer.clear()
        self._clear_cards()
        self._file_label.setText("No report selected")
        self.refresh()

    def _open_folder(self) -> None:
        """Navigate to outputs/reports/ — shown inside the app as a refresh."""
        abs_dir = os.path.abspath(_REPORTS_DIR)
        os.makedirs(abs_dir, exist_ok=True)
        # Show the path so the user knows where it is, then refresh
        QMessageBox.information(
            self,
            "Reports Folder",
            f"Reports are stored in:\n{abs_dir}",
        )
        self.refresh()
