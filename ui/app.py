"""
app.py - Main application window for the Ball Detection & Tracking System.

Integrates CameraController (backend) with the PySide6 UI.
No cv2.imshow() windows are opened; frames are rendered inside FeedWidget.
"""

import sys
from datetime import datetime
from typing import Optional
import os
import subprocess

from PySide6.QtCore import (
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.controller import CameraController
from ui.settings_page import SettingsPage
from ui.theme import (
    ACCENT,
    FONT_FAMILY,
    STYLESHEET,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from ui.widgets import HDivider, ModeBadge, NavButton, StatCard


# ── Camera Feed Widget ────────────────────────────────────────────────────────

class FeedWidget(QWidget):
    """
    Displays live camera frames inside a QLabel, maintaining 16:9 aspect ratio.
    Falls back to a styled placeholder when the camera is stopped or unavailable.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel()
        self._label.setObjectName("feedPlaceholder")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # Smooth pixmap scaling
        self._label.setScaledContents(False)
        layout.addWidget(self._label)

        self._current_pixmap: QPixmap | None = None
        self._show_placeholder("Press  Start  to begin", icon="📷")

    # ── Public API ────────────────────────────────────────────────────────────

    def update_frame(self, pixmap: QPixmap) -> None:
        """Render a new camera frame, scaled to fit while keeping 16:9."""
        self._current_pixmap = pixmap
        self._render_scaled(pixmap)

    def show_error(self, message: str) -> None:
        """Display an error state (e.g. 'Camera Not Available')."""
        self._current_pixmap = None
        self._show_placeholder(message, icon="⚠️", error=True)

    def show_idle(self) -> None:
        """Restore the default 'Press Start' placeholder."""
        self._current_pixmap = None
        self._show_placeholder("Press  Start  to begin", icon="📷")

    def show_stopped(self) -> None:
        """Show a distinct stopped state placeholder."""
        self._current_pixmap = None
        self._show_placeholder("Session stopped", icon="⏹️")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _show_placeholder(
        self, message: str, icon: str = "📷", error: bool = False
    ) -> None:
        colour = "#ff3b3b" if error else TEXT_SECONDARY
        self._label.setPixmap(QPixmap())          # clear any live frame
        self._label.setText(
            "<div style='text-align:center; line-height:1.8;'>"
            f"<span style='font-size:40px;'>{icon}</span><br>"
            f"<span style='font-size:15px; color:{colour};'>{message}</span>"
            "</div>"
        )
        self._label.setTextFormat(Qt.TextFormat.RichText)

    def _render_scaled(self, pixmap: QPixmap) -> None:
        """Scale pixmap to fit the label area, preserving aspect ratio."""
        target = self._target_size()
        scaled = pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._label.setPixmap(scaled)
        self._label.setText("")

    def _target_size(self) -> QSize:
        """Return the largest 16:9 QSize that fits within the current widget."""
        w = self._label.width()
        h = self._label.height()
        target_h = int(w * 9 / 16)
        if target_h <= h:
            return QSize(w, target_h)
        target_w = int(h * 16 / 9)
        return QSize(target_w, h)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Re-scale the live frame on window resize
        if self._current_pixmap is not None:
            self._render_scaled(self._current_pixmap)


# ── Top Bar ───────────────────────────────────────────────────────────────────

class TopBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 10, 0)
        layout.setSpacing(0)

        # ── Left: logo + title
        logo = QLabel("🎯")
        logo.setFont(QFont(FONT_FAMILY, 16))
        logo.setStyleSheet("background: transparent;")

        title = QLabel("Ball Detection & Tracking System")
        title.setFont(QFont(FONT_FAMILY, 13, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent; margin-left: 8px;")

        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addStretch()

        # ── Centre: mode badge
        self.mode_badge = ModeBadge()
        layout.addWidget(self.mode_badge)
        layout.addStretch()

        # ── Right: start / stop + window controls
        self.start_btn = QPushButton("▶  Start")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setFixedHeight(32)

        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setFixedHeight(32)

        layout.addWidget(self.start_btn)
        layout.addSpacing(8)
        layout.addWidget(self.stop_btn)
        layout.addSpacing(16)

        for symbol, name, tip in [("─", "minBtn", "Minimise"),
                                   ("□", "maxBtn", "Maximise"),
                                   ("✕", "closeBtn", "Close")]:
            btn = QPushButton(symbol)
            btn.setObjectName("winBtn")
            btn.setFixedSize(QSize(32, 32))
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if name == "closeBtn":
                btn.setObjectName("closeBtn")
                btn.clicked.connect(QApplication.instance().quit)
            elif name == "minBtn":
                btn.clicked.connect(parent.showMinimized if parent else lambda: None)
            elif name == "maxBtn":
                btn.clicked.connect(self._toggle_max)
            layout.addWidget(btn)

    def _toggle_max(self):
        win = self.window()
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()


# ── Sidebar ───────────────────────────────────────────────────────────────────

class Sidebar(QWidget):
    page_selected = Signal(str)   # emits the nav label, e.g. "Settings"

    _NAV_ITEMS = [
        ("🏠", "Dashboard"),
        ("📹", "Live Feed"),
        ("📊", "Statistics"),
        ("📄", "Reports"),
        ("⚙️",  "Settings"),
        ("ℹ️",  "About"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(190)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(2)

        self._nav_btns: list[NavButton] = []

        for icon, label in self._NAV_ITEMS:
            btn = NavButton(icon, label, self)
            btn.clicked.connect(lambda _, b=btn, lbl=label: self._on_btn(b, lbl))
            layout.addWidget(btn)
            self._nav_btns.append(btn)

        # Activate Dashboard by default
        self._activate(self._nav_btns[0])

        layout.addStretch()
        layout.addWidget(HDivider())

        # ── Status section
        self._status_lbl  = self._status_row("⬤", "Camera", "Offline")
        self._date_lbl    = self._info_label("")
        self._time_lbl    = self._info_label("")

        layout.addSpacing(6)
        layout.addWidget(self._status_lbl)
        layout.addSpacing(4)
        layout.addWidget(self._date_lbl)
        layout.addWidget(self._time_lbl)

        self._refresh_clock()
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._refresh_clock)
        self._clock_timer.start(1000)

    # helpers
    def _status_row(self, dot: str, label: str, value: str) -> QLabel:
        lbl = QLabel(f"<span style='color:#ff3b3b;'>{dot}</span>  {label}: {value}")
        lbl.setFont(QFont(FONT_FAMILY, 10))
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent; padding-left: 6px;")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        self._cam_status_widget = lbl
        return lbl

    def _info_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont(FONT_FAMILY, 10))
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent; padding-left: 6px;")
        return lbl

    def _on_btn(self, btn: NavButton, label: str) -> None:
        self._activate(btn)
        self.page_selected.emit(label)

    def _activate(self, active_btn: NavButton) -> None:
        for btn in self._nav_btns:
            btn.set_active(btn is active_btn)

    def _refresh_clock(self) -> None:
        now = datetime.now()
        self._date_lbl.setText(f"  📅  {now.strftime('%d %b %Y')}")
        self._time_lbl.setText(f"  🕐  {now.strftime('%H:%M:%S')}")

    def set_camera_status(self, online: bool) -> None:
        dot_colour = ACCENT if online else "#ff3b3b"
        state = "Online" if online else "Offline"
        self._cam_status_widget.setText(
            f"<span style='color:{dot_colour};'>⬤</span>  Camera: {state}"
        )


# ── Right Panel ───────────────────────────────────────────────────────────────

class RightPanel(QWidget):
    _CARDS = [
        ("⚡", "FPS",          "0.0"),
        ("🎯", "Detections",   "0"),
        ("🔖", "Track ID",     "—"),
        ("💨", "Speed",        "0 px/s"),
        ("✅", "Confidence",   "0.00"),
        ("⏱️", "Session Time", "00:00"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(10)

        title = QLabel("Live Statistics")
        title.setFont(QFont(FONT_FAMILY, 13, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(title)
        layout.addWidget(HDivider())
        layout.addSpacing(4)

        self._stat_cards: dict[str, StatCard] = {}
        for icon, label, default in self._CARDS:
            card = StatCard(icon, label, default, self)
            self._stat_cards[label] = card
            layout.addWidget(card)

        layout.addStretch()

    def update_stat(self, label: str, value: str) -> None:
        """Update a single stat card by its label name."""
        if label in self._stat_cards:
            self._stat_cards[label].set_value(value)


# ── Bottom Bar ────────────────────────────────────────────────────────────────

class BottomBar(QWidget):
    _ACTIONS = [
        ("📷", "Capture Frame"),
        ("📋", "JSON Report"),
        ("📝", "TXT Report"),
        ("💾", "Export Session"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("bottomBar")
        self.setFixedHeight(54)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        self.action_buttons: dict[str, QPushButton] = {}

        for icon, label in self._ACTIONS:
            btn = QPushButton(f"{icon}  {label}")
            btn.setObjectName("actionBtn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
            layout.addWidget(btn)
            self.action_buttons[label] = btn

        layout.addStretch()


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QWidget):
    """Top-level application window with live camera integration."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("centralWidget")
        self.setWindowTitle("Ball Detection & Tracking System")
        self.setMinimumSize(1100, 680)
        self.resize(1360, 780)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar
        self.top_bar = TopBar(self)
        root.addWidget(self.top_bar)

        # ── Body (sidebar + feed + right panel)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.sidebar = Sidebar(self)
        body.addWidget(self.sidebar)

        # ── Centre: stacked widget (feed page + settings page) ────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        # Page 0 — live feed (+ optional HSV mask panel side by side)
        feed_page = QWidget()
        feed_page.setObjectName("centralWidget")
        feed_layout = QVBoxLayout(feed_page)
        feed_layout.setContentsMargins(16, 16, 16, 16)
        feed_layout.setSpacing(10)

        # Inner row: main feed | mask panel
        feed_row = QHBoxLayout()
        feed_row.setSpacing(12)

        self.feed = FeedWidget(feed_page)
        feed_row.addWidget(self.feed, stretch=2)

        # HSV mask panel — hidden by default
        self._mask_panel = FeedWidget(feed_page)
        self._mask_panel.setVisible(False)
        # Label it so the user knows what they're looking at
        self._mask_panel._show_placeholder("HSV Mask", icon="🎭")
        feed_row.addWidget(self._mask_panel, stretch=1)

        feed_layout.addLayout(feed_row)
        self._stack.addWidget(feed_page)          # index 0

        # Page 1 — settings
        self._settings_page_placeholder = None    # created lazily after controller
        self._stack.addWidget(QWidget())          # index 1 placeholder

        body.addWidget(self._stack, stretch=1)

        self.right_panel = RightPanel(self)
        body.addWidget(self.right_panel)

        root.addLayout(body, stretch=1)

        # ── Bottom bar
        self.bottom_bar = BottomBar(self)
        root.addWidget(self.bottom_bar)

        # ── Camera controller ─────────────────────────────────────────────────
        self._controller = CameraController(self)
        self._controller.frame_ready.connect(self.feed.update_frame)
        self._controller.mask_ready.connect(self._mask_panel.update_frame)
        self._controller.camera_online.connect(self._on_camera_online)
        self._controller.error.connect(self._on_camera_error)
        self._controller.stats_updated.connect(self._on_stats_updated)

        self.top_bar.start_btn.clicked.connect(self._start_camera)
        self.top_bar.stop_btn.clicked.connect(self._stop_camera)

        # Replace the placeholder settings page with the real one (needs controller)
        real_settings = SettingsPage(self._controller.config, self)
        self._stack.removeWidget(self._stack.widget(1))
        self._stack.insertWidget(1, real_settings)

        # Wire sidebar navigation to stack pages
        self.sidebar.page_selected.connect(self._on_nav)

        # Restore persisted UI state that requires the widget to exist first
        self._mask_panel.setVisible(self._controller.config.show_hsv_mask)

        # Initial button state: Start enabled, Stop disabled
        self._set_button_states(running=False)

        # ── Bottom bar actions ────────────────────────────────────────────────
        btns = self.bottom_bar.action_buttons
        btns["Capture Frame"].clicked.connect(self._capture_frame)
        btns["JSON Report"].clicked.connect(self._open_json_report)
        btns["TXT Report"].clicked.connect(self._open_txt_report)
        btns["Export Session"].clicked.connect(self._export_session)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _on_nav(self, label: str) -> None:
        """Switch the centre stack based on the sidebar item clicked."""
        if label == "Settings":
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)

    # ── Camera slot handlers ──────────────────────────────────────────────────

    def _start_camera(self) -> None:
        """Start the pipeline; guard against double-press."""
        if self._controller.is_running:
            return
        self._set_button_states(running=True)
        self.feed.show_idle()          # clear any previous error before starting
        self._controller.start()

    def _stop_camera(self) -> None:
        """Stop the pipeline; leave the app running so Start can be used again."""
        self._controller.stop()        # releases camera + stops timer
        self._set_button_states(running=False)
        self.feed.show_stopped()       # distinct stopped placeholder
        self._reset_stats()            # zero-out right panel cards

    def _set_button_states(self, running: bool) -> None:
        """Grey out whichever button is not applicable right now."""
        self.top_bar.start_btn.setEnabled(not running)
        self.top_bar.stop_btn.setEnabled(running)
        # Dim the disabled button visually via opacity
        self.top_bar.start_btn.setStyleSheet(
            "" if not running else "opacity: 0.4;"
        )
        self.top_bar.stop_btn.setStyleSheet(
            "" if running else "opacity: 0.4;"
        )

    def _reset_stats(self) -> None:
        """Reset all stat cards to their zero / idle defaults."""
        defaults = {
            "FPS":          "0.0",
            "Detections":   "0",
            "Track ID":     "—",
            "Speed":        "0.0 px/s",
            "Confidence":   "0.00",
            "Session Time": "00:00",
        }
        for label, value in defaults.items():
            self.right_panel.update_stat(label, value)

    def _on_camera_online(self, online: bool) -> None:
        self.sidebar.set_camera_status(online)
        # Camera just came online → SEARCHING until first detection
        # Camera went offline (via Stop) → handled by _stop_camera already
        if online:
            self.set_mode("SEARCHING")
        else:
            self.set_mode("STOPPED")

    def _on_camera_error(self, message: str) -> None:
        """Camera failed to open or disconnected mid-session."""
        self.feed.show_error(message)
        self.sidebar.set_camera_status(False)
        self.set_mode("STOPPED")
        self._set_button_states(running=False)
        self._reset_stats()

    def _on_stats_updated(self, stats: dict) -> None:
        """Push live per-frame stats to the right-panel cards and mode badge."""
        mapping = {
            "fps":          "FPS",
            "detections":   "Detections",
            "track_id":     "Track ID",
            "speed":        "Speed",
            "confidence":   "Confidence",
            "session_time": "Session Time",
        }
        for key, label in mapping.items():
            if key in stats:
                self.right_panel.update_stat(label, stats[key])

        # Mode badge follows tracking state in real time
        track_id = stats.get("track_id", "—")
        self.set_mode("TRACKING" if track_id != "—" else "SEARCHING")

    # ── Bottom bar handlers ───────────────────────────────────────────────────

    def _capture_frame(self) -> None:
        """Save the current annotated frame as a PNG inside outputs/frames/."""
        pixmap: Optional[QPixmap] = self._controller.last_pixmap
        if pixmap is None or pixmap.isNull():
            self._alert("No frame available. Start the camera first.")
            return

        out_dir = os.path.join("outputs", "frames")
        os.makedirs(out_dir, exist_ok=True)
        filename = datetime.now().strftime("frame_%Y%m%d_%H%M%S.png")
        dest = os.path.abspath(os.path.join(out_dir, filename))

        if pixmap.save(dest, "PNG"):
            self._alert(f"Frame saved:\n{dest}", title="Capture Frame", info=True)
        else:
            self._alert("Failed to save frame.")

    def _open_json_report(self) -> None:
        """Open the last-generated JSON report in the default system viewer."""
        path = self._controller.json_report_path
        if not os.path.isfile(path):
            self._alert(
                "No JSON report found.\nUse  Export Session  to generate one first."
            )
            return
        self._open_file(path)

    def _open_txt_report(self) -> None:
        """Open the last-generated TXT report in the default system viewer."""
        path = self._controller.txt_report_path
        if not os.path.isfile(path):
            self._alert(
                "No TXT report found.\nUse  Export Session  to generate one first."
            )
            return
        self._open_file(path)

    def _export_session(self) -> None:
        """Generate the latest report from current backend data and save both files."""
        try:
            json_path, txt_path = self._controller.export_session()
            self._alert(
                f"Session exported:\n{json_path}\n{txt_path}",
                title="Export Session",
                info=True,
            )
        except Exception as exc:
            self._alert(f"Export failed:\n{exc}")

    # ── Utility helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _open_file(path: str) -> None:
        """Open a file with the OS default application (cross-platform)."""
        import platform
        system = platform.system()
        if system == "Windows":
            os.startfile(path)              # noqa: S606
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    @staticmethod
    def _alert(
        message: str, title: str = "Ball Tracker", info: bool = False
    ) -> None:
        """Show a brief modal message box."""
        box = QMessageBox()
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon(
            QMessageBox.Icon.Information if info else QMessageBox.Icon.Warning
        )
        box.exec()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Ensure the camera is released cleanly when the window closes."""
        self._controller.stop()
        super().closeEvent(event)

    # ── Public helpers ────────────────────────────────────────────────────────

    def set_mode(self, mode: str) -> None:
        """Update the top-bar mode badge. mode: TRACKING | SEARCHING | STOPPED"""
        self.top_bar.mode_badge.set_mode(mode)

    def update_stat(self, label: str, value: str) -> None:
        self.right_panel.update_stat(label, value)

    def set_camera_status(self, online: bool) -> None:
        self.sidebar.set_camera_status(online)

    def set_mask_visible(self, visible: bool) -> None:
        """Show or hide the HSV mask debug panel beside the live feed."""
        self._mask_panel.setVisible(visible)
        if not visible:
            self._mask_panel._show_placeholder("HSV Mask", icon="🎭")


# ── Entry point ───────────────────────────────────────────────────────────────

def launch() -> None:
    """Create the QApplication and show the main window."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    app.setFont(QFont(FONT_FAMILY, 10))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    launch()
