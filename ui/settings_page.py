"""
settings_page.py - Settings panel for the Ball Detection & Tracking System.

Writes changes directly to RuntimeConfig (held by the controller) so they
take effect on the very next frame tick — no restart required.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.theme import (
    ACCENT,
    BG_CARD,
    BG_PANEL,
    BORDER,
    FONT_FAMILY,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


# ── Stylesheet fragments ──────────────────────────────────────────────────────

_SECTION_STYLE = f"""
    QWidget#settingSection {{
        background: {BG_CARD};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
"""

_SLIDER_STYLE = f"""
    QSlider::groove:horizontal {{
        height: 4px;
        background: {BORDER};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {ACCENT};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
    }}
    QSlider::sub-page:horizontal {{
        background: {ACCENT};
        border-radius: 2px;
    }}
"""

_COMBO_STYLE = f"""
    QComboBox {{
        background: #222;
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 4px 10px;
        color: {TEXT_PRIMARY};
        min-width: 140px;
    }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background: #222;
        border: 1px solid {BORDER};
        selection-background-color: #2a2a2a;
        color: {TEXT_PRIMARY};
    }}
"""

_SPIN_STYLE = f"""
    QSpinBox {{
        background: #222;
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 4px 8px;
        color: {TEXT_PRIMARY};
        min-width: 60px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; }}
"""

_CHECK_STYLE = f"""
    QCheckBox {{
        color: {TEXT_PRIMARY};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 18px; height: 18px;
        border: 2px solid {BORDER};
        border-radius: 4px;
        background: #222;
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _heading(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT_FAMILY, 11, QFont.Weight.DemiBold))
    lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
    return lbl


def _caption(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT_FAMILY, 9))
    lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
    return lbl


def _row_label(text: str, width: int = 180) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT_FAMILY, 10))
    lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
    lbl.setFixedWidth(width)
    return lbl


class _Section(QWidget):
    """A card-styled container for a group of settings rows."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("settingSection")
        self.setStyleSheet(_SECTION_STYLE)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(12)
        self._layout.addWidget(_heading(title))

    def add_row(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)

    def add_widget(self, widget: QWidget) -> None:
        self._layout.addWidget(widget)


# ── Settings Page ─────────────────────────────────────────────────────────────

class SettingsPage(QWidget):
    """
    Full settings panel.  Writes changes immediately to the controller's
    RuntimeConfig so they apply on the next pipeline tick.
    """

    def __init__(self, config, parent=None) -> None:
        """
        Args:
            config: RuntimeConfig instance owned by CameraController.
        """
        super().__init__(parent)
        self._cfg = config
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {BG_PANEL};")

        # Scrollable content area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {BG_PANEL}; border: none;")

        content = QWidget()
        content.setStyleSheet(f"background: {BG_PANEL};")
        self._form = QVBoxLayout(content)
        self._form.setContentsMargins(20, 20, 20, 20)
        self._form.setSpacing(16)

        # Page title
        title = QLabel("Settings")
        title.setFont(QFont(FONT_FAMILY, 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        self._form.addWidget(title)
        self._form.addWidget(_caption("Changes apply immediately — no restart needed."))
        self._form.addSpacing(4)

        self._build_camera_section()
        self._build_display_section()
        self._build_detection_section()

        self._form.addStretch()
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Section builders ──────────────────────────────────────────────────────

    def _build_camera_section(self) -> None:
        sec = _Section("📷  Camera")

        # Camera Index (SpinBox 0–9)
        row = QHBoxLayout()
        row.addWidget(_row_label("Camera Index"))
        self._cam_index = QSpinBox()
        self._cam_index.setRange(0, 9)
        self._cam_index.setValue(self._cfg.camera_index)
        self._cam_index.setToolTip(
            "Device index passed to cv2.VideoCapture().\n"
            "Takes effect the next time you press Start."
        )
        self._cam_index.setStyleSheet(_SPIN_STYLE)
        row.addWidget(self._cam_index)
        row.addWidget(_caption("  (restart capture to apply)"))
        row.addStretch()
        w = QWidget(); w.setLayout(row); w.setStyleSheet("background:transparent")
        sec.add_row(w)

        # Resolution dropdown
        row2 = QHBoxLayout()
        row2.addWidget(_row_label("Resolution"))
        self._resolution = QComboBox()
        self._resolution.setStyleSheet(_COMBO_STYLE)
        for label, (w_, h_) in self._cfg.RESOLUTIONS.items():
            self._resolution.addItem(label, (w_, h_))
        # Select current
        cur = f"{self._cfg.frame_width}×{self._cfg.frame_height}"
        idx = self._resolution.findText(cur)
        if idx >= 0:
            self._resolution.setCurrentIndex(idx)
        self._resolution.setToolTip("Resolution applied the next time you press Start.")
        row2.addWidget(self._resolution)
        row2.addWidget(_caption("  (restart capture to apply)"))
        row2.addStretch()
        w2 = QWidget(); w2.setLayout(row2); w2.setStyleSheet("background:transparent")
        sec.add_row(w2)

        self._form.addWidget(sec)

        # Wire signals last to avoid firing during construction
        self._cam_index.valueChanged.connect(self._on_cam_index)
        self._resolution.currentIndexChanged.connect(self._on_resolution)

    def _build_display_section(self) -> None:
        sec = _Section("🖥️  Display")

        # Show FPS
        self._show_fps = QCheckBox("Show FPS overlay on live feed")
        self._show_fps.setChecked(self._cfg.show_fps)
        self._show_fps.setStyleSheet(_CHECK_STYLE)
        self._show_fps.toggled.connect(self._on_show_fps)
        sec.add_widget(self._show_fps)

        # Show Trajectory
        self._show_traj = QCheckBox("Show trajectory trails")
        self._show_traj.setChecked(self._cfg.show_trajectory)
        self._show_traj.setStyleSheet(_CHECK_STYLE)
        self._show_traj.toggled.connect(self._on_show_trajectory)
        sec.add_widget(self._show_traj)

        self._form.addWidget(sec)

    def _build_detection_section(self) -> None:
        sec = _Section("🎯  Detection")

        # Confidence Threshold slider (0.1 – 1.0, step 0.05)
        row = QVBoxLayout()

        header = QHBoxLayout()
        header.addWidget(_row_label("Confidence Threshold"))
        self._conf_val_lbl = QLabel(f"{self._cfg.confidence_threshold:.2f}")
        self._conf_val_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
        self._conf_val_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent;")
        self._conf_val_lbl.setFixedWidth(36)
        header.addWidget(self._conf_val_lbl)
        header.addStretch()

        self._conf_slider = QSlider(Qt.Orientation.Horizontal)
        self._conf_slider.setRange(5, 95)          # maps to 0.05 – 0.95
        self._conf_slider.setValue(
            int(self._cfg.confidence_threshold * 100)
        )
        self._conf_slider.setStyleSheet(_SLIDER_STYLE)
        self._conf_slider.setToolTip(
            "Detections below this score are discarded.\n"
            "Lower = more detections (more noise).\n"
            "Higher = fewer detections (more precise)."
        )
        self._conf_slider.valueChanged.connect(self._on_confidence)

        range_row = QHBoxLayout()
        range_row.addWidget(_caption("0.05"))
        range_row.addStretch()
        range_row.addWidget(_caption("0.95"))

        w_header = QWidget(); w_header.setLayout(header)
        w_header.setStyleSheet("background:transparent")
        w_slider = QWidget(); w_slider.setLayout(
            (lambda l: (l.addWidget(self._conf_slider), l)[1])(QVBoxLayout())
        )
        # simpler: just add directly
        row.addLayout(header)
        row.addWidget(self._conf_slider)
        row.addLayout(range_row)

        row_w = QWidget(); row_w.setLayout(row)
        row_w.setStyleSheet("background:transparent")
        sec.add_widget(row_w)

        self._form.addWidget(sec)

    # ── Signal handlers ───────────────────────────────────────────────────────

    def _on_cam_index(self, value: int) -> None:
        self._cfg.camera_index = value

    def _on_resolution(self, _index: int) -> None:
        w, h = self._resolution.currentData()
        self._cfg.frame_width  = w
        self._cfg.frame_height = h

    def _on_show_fps(self, checked: bool) -> None:
        self._cfg.show_fps = checked

    def _on_show_trajectory(self, checked: bool) -> None:
        self._cfg.show_trajectory = checked

    def _on_confidence(self, raw: int) -> None:
        value = raw / 100.0
        self._cfg.confidence_threshold = value
        self._conf_val_lbl.setText(f"{value:.2f}")
