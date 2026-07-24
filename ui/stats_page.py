"""
stats_page.py - Live Statistics page with animated FPS and Speed graphs.

Consumes the existing CameraController.stats_updated signal dict:
    {
        "fps":          str  e.g. "30.2"
        "speed":        str  e.g. "145.7 px/s"
        "session_time": str  e.g. "01:23"
        ...
    }

Uses PySide6.QtCharts — no extra dependencies required.
"""

from collections import deque
from typing import Deque

from PySide6.QtCharts import (
    QChart,
    QChartView,
    QLineSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
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

# Rolling history length
_HISTORY = 150


# ── Helpers ───────────────────────────────────────────────────────────────────

def _label(text: str, size: int = 10, bold: bool = False, colour: str = TEXT_PRIMARY) -> QLabel:
    lbl = QLabel(text)
    w = QFont.Weight.Bold if bold else QFont.Weight.Normal
    lbl.setFont(QFont(FONT_FAMILY, size, w))
    lbl.setStyleSheet(f"color: {colour}; background: transparent;")
    return lbl


def _value_label(text: str = "—") -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont(FONT_MONO, 15, QFont.Weight.Bold))
    lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return lbl


# ── Summary Row ───────────────────────────────────────────────────────────────

class _SummaryRow(QWidget):
    """A horizontal row of three labelled stat values (Current / Avg / Max)."""

    def __init__(self, icon: str, metric: str, unit: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_CARD}; border-radius: 8px;")
        self._unit = unit

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(0)

        # Left: icon + metric name
        left = QHBoxLayout()
        left.setSpacing(8)
        left.addWidget(_label(icon, size=14, colour=ACCENT))
        left.addWidget(_label(metric, size=11, bold=True))
        left.addStretch()
        layout.addLayout(left, stretch=3)

        # Three stat columns
        self._cur  = _value_label()
        self._avg  = _value_label()
        self._max  = _value_label()

        for header, widget in [("Current", self._cur),
                                ("Average", self._avg),
                                ("Maximum", self._max)]:
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(_label(header, size=8, colour=TEXT_SECONDARY),
                          alignment=Qt.AlignmentFlag.AlignRight)
            col.addWidget(widget)
            layout.addLayout(col, stretch=2)

    def update_values(self, cur: float, avg: float, maximum: float) -> None:
        def fmt(v: float) -> str:
            return f"{v:.1f}{self._unit}"
        self._cur.setText(fmt(cur))
        self._avg.setText(fmt(avg))
        self._max.setText(fmt(maximum))


# ── Live Chart ────────────────────────────────────────────────────────────────

class _LiveChart(QChartView):
    """
    A QChartView wrapper that holds a single QLineSeries updated in-place.
    Replacing series points is O(n) but n ≤ 150, well within the ~30 fps budget.
    """

    def __init__(
        self,
        title: str,
        colour: str,
        y_label: str,
        y_min: float = 0.0,
        y_max: float = 60.0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(200)

        # Series
        self._series = QLineSeries()
        pen = QPen(QColor(colour))
        pen.setWidth(2)
        self._series.setPen(pen)

        # Chart
        chart = QChart()
        chart.addSeries(self._series)
        chart.setTitle(title)
        chart.setBackgroundBrush(QColor(BG_CARD))
        chart.setBackgroundRoundness(8)
        chart.setMargins(__import__("PySide6.QtCore", fromlist=["QMargins"]).QMargins(8, 8, 8, 8))
        chart.legend().hide()

        # Title font
        title_font = QFont(FONT_FAMILY, 10, QFont.Weight.DemiBold)
        chart.setTitleFont(title_font)
        chart.setTitleBrush(QColor(TEXT_PRIMARY))

        # X axis — sample index
        self._x_axis = QValueAxis()
        self._x_axis.setRange(0, _HISTORY)
        self._x_axis.setLabelsVisible(False)
        self._x_axis.setGridLineColor(QColor(BORDER))
        self._x_axis.setLinePen(QPen(QColor(BORDER)))
        chart.addAxis(self._x_axis, Qt.AlignmentFlag.AlignBottom)
        self._series.attachAxis(self._x_axis)

        # Y axis
        self._y_axis = QValueAxis()
        self._y_axis.setRange(y_min, y_max)
        self._y_axis.setTitleText(y_label)
        self._y_axis.setTitleFont(QFont(FONT_FAMILY, 8))
        self._y_axis.setTitleBrush(QColor(TEXT_SECONDARY))
        self._y_axis.setLabelsFont(QFont(FONT_MONO, 8))
        self._y_axis.setLabelsBrush(QColor(TEXT_SECONDARY))
        self._y_axis.setGridLineColor(QColor(BORDER))
        self._y_axis.setLinePen(QPen(QColor(BORDER)))
        self._y_axis.setTickCount(5)
        chart.addAxis(self._y_axis, Qt.AlignmentFlag.AlignLeft)
        self._series.attachAxis(self._y_axis)

        self.setChart(chart)
        self.setStyleSheet(f"background: {BG_CARD}; border-radius: 8px; border: 1px solid {BORDER};")

        self._data: Deque[float] = deque(maxlen=_HISTORY)
        self._y_max = y_max

    def push(self, value: float) -> None:
        """Append a value and redraw the series."""
        self._data.append(value)

        # Auto-scale Y if value exceeds current max (with 20 % headroom)
        if value > self._y_max:
            self._y_max = value * 1.2
            self._y_axis.setRange(0, self._y_max)

        # Replace all points in one call — avoids flicker from incremental appends
        points = [
            __import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(i, v)
            for i, v in enumerate(self._data)
        ]
        self._series.replace(points)

    def reset(self) -> None:
        """Clear all data."""
        self._data.clear()
        self._series.clear()


# ── Statistics Page ───────────────────────────────────────────────────────────

class StatisticsPage(QWidget):
    """
    Live Statistics page.  Call push_stats(stats_dict) each time the
    controller's stats_updated signal fires.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PANEL};")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Running accumulators (session-level) ──────────────────────────────
        self._fps_history:   Deque[float] = deque(maxlen=_HISTORY)
        self._speed_history: Deque[float] = deque(maxlen=_HISTORY)
        self._fps_max:   float = 0.0
        self._speed_max: float = 0.0

        # ── Scroll wrapper ────────────────────────────────────────────────────
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {BG_PANEL}; border: none;")

        content = QWidget()
        content.setStyleSheet(f"background: {BG_PANEL};")
        form = QVBoxLayout(content)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(14)

        # Page title
        form.addWidget(_label("Statistics", size=16, bold=True))
        form.addWidget(_label("Live FPS and speed graphs — updates in real time.",
                              size=9, colour=TEXT_SECONDARY))
        form.addSpacing(4)

        # ── Summary rows ──────────────────────────────────────────────────────
        self._fps_row   = _SummaryRow("⚡", "FPS",         unit=" fps")
        self._speed_row = _SummaryRow("💨", "Ball Speed",  unit=" px/s")
        form.addWidget(self._fps_row)
        form.addWidget(self._speed_row)
        form.addSpacing(6)

        # ── Charts ────────────────────────────────────────────────────────────
        self._fps_chart   = _LiveChart("FPS over Time",        ACCENT,    "FPS",    0, 60)
        self._speed_chart = _LiveChart("Ball Speed over Time", "#00bfff", "px/s",   0, 300)

        form.addWidget(self._fps_chart)
        form.addSpacing(8)
        form.addWidget(self._speed_chart)
        form.addStretch()

        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Public API ────────────────────────────────────────────────────────────

    def push_stats(self, stats: dict) -> None:
        """
        Ingest one stats_updated dict from CameraController and refresh the UI.

        Args:
            stats: dict with at least keys "fps" (str) and "speed" (str).
        """
        fps   = self._parse_fps(stats.get("fps", "0"))
        speed = self._parse_speed(stats.get("speed", "0 px/s"))

        # Accumulate history
        self._fps_history.append(fps)
        self._speed_history.append(speed)

        if fps   > self._fps_max:   self._fps_max   = fps
        if speed > self._speed_max: self._speed_max = speed

        avg_fps   = sum(self._fps_history)   / len(self._fps_history)
        avg_speed = sum(self._speed_history) / len(self._speed_history)

        # Update summary rows
        self._fps_row.update_values(fps,   avg_fps,   self._fps_max)
        self._speed_row.update_values(speed, avg_speed, self._speed_max)

        # Push to charts
        self._fps_chart.push(fps)
        self._speed_chart.push(speed)

    def reset(self) -> None:
        """Clear all accumulated history (call when a new session starts)."""
        self._fps_history.clear()
        self._speed_history.clear()
        self._fps_max   = 0.0
        self._speed_max = 0.0
        self._fps_chart.reset()
        self._speed_chart.reset()
        self._fps_row.update_values(0, 0, 0)
        self._speed_row.update_values(0, 0, 0)

    # ── Parsing helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_fps(raw: str) -> float:
        """Parse "30.2" → 30.2; return 0.0 on failure."""
        try:
            return float(raw)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _parse_speed(raw: str) -> float:
        """Parse "145.7 px/s" → 145.7; return 0.0 on failure."""
        try:
            return float(raw.split()[0])
        except (ValueError, TypeError, IndexError):
            return 0.0
