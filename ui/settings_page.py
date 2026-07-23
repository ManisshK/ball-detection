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
            config:  RuntimeConfig instance owned by CameraController.
            parent:  Should be the MainWindow so set_mask_visible() can be called.
        """
        super().__init__(parent)
        self._cfg = config
        self._main_window = parent  # may be None in unit-test contexts
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
        self._build_hsv_section()
        self._build_preprocessing_section()

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

        # Show HSV Mask (debug)
        self._show_mask = QCheckBox("Show HSV Mask  (debug)")
        self._show_mask.setChecked(self._cfg.show_hsv_mask)
        self._show_mask.setStyleSheet(_CHECK_STYLE)
        self._show_mask.setToolTip(
            "Displays the binary HSV mask beside the live feed.\n"
            "Useful for tuning HSV colour range sliders."
        )
        self._show_mask.toggled.connect(self._on_show_mask)
        sec.add_widget(self._show_mask)

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

        # ── Minimum Area ──────────────────────────────────────────────────────
        area_row = QVBoxLayout()

        area_header = QHBoxLayout()
        area_header.addWidget(_row_label("Minimum Area (px²)"))
        self._area_val_lbl = QLabel(str(self._cfg.min_area))
        self._area_val_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
        self._area_val_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent;")
        self._area_val_lbl.setFixedWidth(48)
        area_header.addWidget(self._area_val_lbl)
        area_header.addStretch()

        self._area_slider = QSlider(Qt.Orientation.Horizontal)
        self._area_slider.setRange(50, 5000)
        self._area_slider.setValue(self._cfg.min_area)
        self._area_slider.setStyleSheet(_SLIDER_STYLE)
        self._area_slider.setToolTip(
            "Contours smaller than this area (px²) are discarded.\n"
            "Raise to ignore small noise blobs."
        )
        self._area_slider.valueChanged.connect(self._on_min_area)

        area_range = QHBoxLayout()
        area_range.addWidget(_caption("50"))
        area_range.addStretch()
        area_range.addWidget(_caption("5000"))

        area_row.addLayout(area_header)
        area_row.addWidget(self._area_slider)
        area_row.addLayout(area_range)

        area_w = QWidget(); area_w.setLayout(area_row)
        area_w.setStyleSheet("background:transparent")
        sec.add_widget(area_w)

        # ── Aspect Ratio Tolerance ────────────────────────────────────────────
        ar_row = QVBoxLayout()

        ar_header = QHBoxLayout()
        ar_header.addWidget(_row_label("Aspect Ratio Tolerance"))
        self._ar_val_lbl = QLabel(f"{self._cfg.aspect_ratio_tolerance:.2f}")
        self._ar_val_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
        self._ar_val_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent;")
        self._ar_val_lbl.setFixedWidth(36)
        ar_header.addWidget(self._ar_val_lbl)
        ar_header.addStretch()

        self._ar_slider = QSlider(Qt.Orientation.Horizontal)
        self._ar_slider.setRange(0, 100)           # maps to 0.0 – 1.0
        self._ar_slider.setValue(int(self._cfg.aspect_ratio_tolerance * 100))
        self._ar_slider.setStyleSheet(_SLIDER_STYLE)
        self._ar_slider.setToolTip(
            "Maximum allowed deviation of width/height from 1:1.\n"
            "0 = circles only.  1 = any shape accepted."
        )
        self._ar_slider.valueChanged.connect(self._on_aspect_ratio)

        ar_range = QHBoxLayout()
        ar_range.addWidget(_caption("0.00  strict"))
        ar_range.addStretch()
        ar_range.addWidget(_caption("1.00  any"))

        ar_row.addLayout(ar_header)
        ar_row.addWidget(self._ar_slider)
        ar_row.addLayout(ar_range)

        ar_w = QWidget(); ar_w.setLayout(ar_row)
        ar_w.setStyleSheet("background:transparent")
        sec.add_widget(ar_w)

        # ── Single Ball Mode ──────────────────────────────────────────────────
        self._single_ball = QCheckBox("Single Ball Mode  (track highest-confidence only)")
        self._single_ball.setChecked(self._cfg.single_ball_mode)
        self._single_ball.setStyleSheet(_CHECK_STYLE)
        self._single_ball.setToolTip(
            "When enabled, detections are sorted by confidence and only\n"
            "the best one is passed to the tracker each frame."
        )
        self._single_ball.toggled.connect(self._on_single_ball)
        sec.add_widget(self._single_ball)

        self._form.addWidget(sec)

    def _build_hsv_section(self) -> None:
        sec = _Section("🎨  HSV Colour Filter")

        # Define the 6 HSV sliders as (attr_name, label, range_max, cfg_attr)
        _sliders = [
            ("_hue_min",  "Hue Min",        179, "hsv_hue_min"),
            ("_hue_max",  "Hue Max",        179, "hsv_hue_max"),
            ("_sat_min",  "Saturation Min", 255, "hsv_sat_min"),
            ("_sat_max",  "Saturation Max", 255, "hsv_sat_max"),
            ("_val_min",  "Value Min",      255, "hsv_val_min"),
            ("_val_max",  "Value Max",      255, "hsv_val_max"),
        ]

        for attr, label_text, max_val, cfg_attr in _sliders:
            row = QVBoxLayout()

            header = QHBoxLayout()
            header.addWidget(_row_label(label_text))
            val_lbl = QLabel(str(getattr(self._cfg, cfg_attr)))
            val_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
            val_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent;")
            val_lbl.setFixedWidth(36)
            header.addWidget(val_lbl)
            header.addStretch()

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, max_val)
            slider.setValue(getattr(self._cfg, cfg_attr))
            slider.setStyleSheet(_SLIDER_STYLE)

            range_row = QHBoxLayout()
            range_row.addWidget(_caption("0"))
            range_row.addStretch()
            range_row.addWidget(_caption(str(max_val)))

            row.addLayout(header)
            row.addWidget(slider)
            row.addLayout(range_row)

            row_w = QWidget()
            row_w.setLayout(row)
            row_w.setStyleSheet("background:transparent")
            sec.add_widget(row_w)

            # Store slider ref and wire signal — capture vars by value
            setattr(self, attr, slider)
            slider.valueChanged.connect(
                lambda v, lbl=val_lbl, key=cfg_attr: self._on_hsv(v, lbl, key)
            )

        self._form.addWidget(sec)

    def _build_preprocessing_section(self) -> None:
        sec = _Section("🔧  Preprocessing")

        # Each entry: (widget_attr, label, min, max, cfg_attr, step, fmt, tooltip)
        _controls = [
            (
                "_morph_k_slider", "Morph Kernel Size",
                1, 21, "morph_kernel_size",
                "Elliptical kernel used for Morphological Open and Close.\n"
                "Larger = removes more noise but may merge nearby blobs.\n"
                "Value is snapped to the nearest odd integer.",
            ),
            (
                "_blur_k_slider", "Gaussian Blur Kernel",
                1, 21, "blur_kernel_size",
                "Gaussian blur applied after morphology to smooth blob edges.\n"
                "Set to 1 to disable blurring entirely.\n"
                "Value is snapped to the nearest odd integer.",
            ),
        ]

        for widget_attr, label_text, lo, hi, cfg_attr, tooltip in _controls:
            row = QVBoxLayout()

            header = QHBoxLayout()
            header.addWidget(_row_label(label_text))
            val_lbl = QLabel(str(getattr(self._cfg, cfg_attr)))
            val_lbl.setFont(QFont(FONT_FAMILY, 10, QFont.Weight.Bold))
            val_lbl.setStyleSheet(f"color: {ACCENT}; background: transparent;")
            val_lbl.setFixedWidth(30)
            header.addWidget(val_lbl)
            header.addStretch()

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(lo, hi)
            slider.setValue(getattr(self._cfg, cfg_attr))
            slider.setSingleStep(2)      # keep snapping to odd values
            slider.setPageStep(2)
            slider.setStyleSheet(_SLIDER_STYLE)
            slider.setToolTip(tooltip)

            range_row = QHBoxLayout()
            range_row.addWidget(_caption(f"{lo}  (off)" if lo == 1 else str(lo)))
            range_row.addStretch()
            range_row.addWidget(_caption(str(hi)))

            row.addLayout(header)
            row.addWidget(slider)
            row.addLayout(range_row)

            row_w = QWidget()
            row_w.setLayout(row)
            row_w.setStyleSheet("background:transparent")
            sec.add_widget(row_w)

            setattr(self, widget_attr, slider)
            slider.valueChanged.connect(
                lambda v, lbl=val_lbl, key=cfg_attr: self._on_kernel(v, lbl, key)
            )

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

    def _on_show_mask(self, checked: bool) -> None:
        self._cfg.show_hsv_mask = checked
        if self._main_window and hasattr(self._main_window, "set_mask_visible"):
            self._main_window.set_mask_visible(checked)

    def _on_confidence(self, raw: int) -> None:
        value = raw / 100.0
        self._cfg.confidence_threshold = value
        self._conf_val_lbl.setText(f"{value:.2f}")

    def _on_hsv(self, value: int, label: QLabel, cfg_attr: str) -> None:
        """Generic handler for all six HSV sliders."""
        setattr(self._cfg, cfg_attr, value)
        label.setText(str(value))

    def _on_min_area(self, value: int) -> None:
        self._cfg.min_area = value
        self._area_val_lbl.setText(str(value))

    def _on_aspect_ratio(self, raw: int) -> None:
        value = raw / 100.0
        self._cfg.aspect_ratio_tolerance = value
        self._ar_val_lbl.setText(f"{value:.2f}")

    def _on_single_ball(self, checked: bool) -> None:
        self._cfg.single_ball_mode = checked

    def _on_kernel(self, value: int, label: QLabel, cfg_attr: str) -> None:
        """Snap to nearest odd integer and write to RuntimeConfig."""
        odd = value if value % 2 == 1 else max(1, value - 1)
        setattr(self._cfg, cfg_attr, odd)
        label.setText(str(odd))
