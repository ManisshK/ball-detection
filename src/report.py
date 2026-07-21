"""
report.py - Session report generation for the ball detection and tracking system.

Consumes a metrics dictionary (as returned by MetricsManager.get_metrics())
plus optional supplementary data and writes structured reports to disk.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

# Default output paths
_REPORTS_DIR = os.path.join("outputs", "reports")
_JSON_PATH = os.path.join(_REPORTS_DIR, "session_report.json")
_TEXT_PATH = os.path.join(_REPORTS_DIR, "session_report.txt")


class ReportGenerator:
    """
    Builds and exports a session summary report.

    Expected metrics dict keys (all optional; missing values default to 0):
        current_fps      - FPS at the last recorded frame
        avg_fps          - Average FPS over the session
        runtime          - Total elapsed seconds
        detection_count  - Cumulative detections (used as 'frames processed')
        lost_tracks      - Cumulative lost tracks

    Supplementary data accepted via generate():
        max_fps          - Peak FPS observed during the session
        avg_ball_speed   - Average ball speed in px/s
        tracks_created   - Total unique tracks created
    """

    def __init__(
        self,
        json_path: str = _JSON_PATH,
        text_path: str = _TEXT_PATH,
    ) -> None:
        """
        Args:
            json_path: Destination path for the JSON report.
            text_path: Destination path for the plain-text report.
        """
        self._json_path = json_path
        self._text_path = text_path
        self._report: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate(
        self,
        metrics: Dict[str, Any],
        max_fps: Optional[float] = None,
        avg_ball_speed: Optional[float] = None,
        tracks_created: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Build the report dictionary from metrics and optional supplementary data.

        Args:
            metrics:        Dict returned by MetricsManager.get_metrics().
            max_fps:        Peak FPS recorded externally (optional).
            avg_ball_speed: Mean ball speed in px/s (optional).
            tracks_created: Total unique tracks initialised (optional).

        Returns:
            The assembled report as a plain dict.
        """
        def _get(key: str, default: Any = 0) -> Any:
            """Safely retrieve a value from the metrics dict."""
            return metrics.get(key, default)

        self._report = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "frames_processed": _get("detection_count"),
            "current_fps": _get("current_fps", 0.0),
            "avg_fps": _get("avg_fps", 0.0),
            "max_fps": round(max_fps, 2) if max_fps is not None else 0.0,
            "avg_ball_speed_px_s": (
                round(avg_ball_speed, 2) if avg_ball_speed is not None else 0.0
            ),
            "tracks_created": tracks_created if tracks_created is not None else 0,
            "tracks_lost": _get("lost_tracks"),
            "total_runtime_s": _get("runtime", 0.0),
        }
        return self._report

    def save_json(self, path: Optional[str] = None) -> str:
        """
        Write the current report to a JSON file.

        Args:
            path: Override output path (uses constructor default if None).

        Returns:
            Absolute path of the written file.

        Raises:
            RuntimeError: If generate() has not been called yet.
        """
        self._ensure_generated()
        dest = path or self._json_path
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as fh:
            json.dump(self._report, fh, indent=2)
        return os.path.abspath(dest)

    def save_text(self, path: Optional[str] = None) -> str:
        """
        Write the current report to a human-readable plain-text file.

        Args:
            path: Override output path (uses constructor default if None).

        Returns:
            Absolute path of the written file.

        Raises:
            RuntimeError: If generate() has not been called yet.
        """
        self._ensure_generated()
        dest = path or self._text_path
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        r = self._report
        lines = [
            "=" * 44,
            "       BALL TRACKING SESSION REPORT",
            "=" * 44,
            f"  Generated      : {r.get('generated_at', 'N/A')}",
            "-" * 44,
            f"  Frames Processed   : {r.get('frames_processed', 0)}",
            f"  Current FPS        : {r.get('current_fps', 0.0):.2f}",
            f"  Average FPS        : {r.get('avg_fps', 0.0):.2f}",
            f"  Maximum FPS        : {r.get('max_fps', 0.0):.2f}",
            f"  Avg Ball Speed     : {r.get('avg_ball_speed_px_s', 0.0):.2f} px/s",
            f"  Tracks Created     : {r.get('tracks_created', 0)}",
            f"  Tracks Lost        : {r.get('tracks_lost', 0)}",
            f"  Total Runtime      : {r.get('total_runtime_s', 0.0):.3f} s",
            "=" * 44,
        ]

        with open(dest, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

        return os.path.abspath(dest)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_generated(self) -> None:
        """Raise RuntimeError if generate() has not been called."""
        if not self._report:
            raise RuntimeError(
                "No report data available. Call generate() before saving."
            )
