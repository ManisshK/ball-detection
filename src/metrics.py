"""
metrics.py - Lightweight real-time metrics tracking for ball detection/tracking.
"""

import json
import time
from typing import Any, Dict, Optional


class MetricsManager:
    """
    Tracks runtime performance and detection statistics.

    Metrics collected:
        - current_fps:    FPS for the most recent frame interval.
        - avg_fps:        Rolling average FPS since start.
        - runtime:        Elapsed seconds since the first update() call.
        - detection_count: Cumulative number of detections seen.
        - lost_tracks:    Cumulative number of tracks that were lost/cleared.
    """

    def __init__(self) -> None:
        """Initialise all counters and timing state."""
        self._start_time: Optional[float] = None
        self._last_time: Optional[float] = None

        self._frame_count: int = 0
        self._current_fps: float = 0.0
        self._avg_fps: float = 0.0

        self._detection_count: int = 0
        self._lost_tracks: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(
        self,
        detections: int = 0,
        lost_tracks: int = 0,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Record metrics for the current frame.

        Call this once per processed frame.

        Args:
            detections:  Number of detections in this frame.
            lost_tracks: Number of tracks lost/dropped this frame.
            timestamp:   Wall-clock time in seconds (defaults to time.time()).
        """
        now = timestamp if timestamp is not None else time.time()

        if self._start_time is None:
            self._start_time = now
            self._last_time = now
            # Nothing to compute on the very first call
            self._detection_count += detections
            self._lost_tracks += lost_tracks
            self._frame_count += 1
            return

        dt = now - self._last_time
        self._current_fps = 1.0 / dt if dt > 0 else 0.0

        self._frame_count += 1
        elapsed = now - self._start_time
        self._avg_fps = self._frame_count / elapsed if elapsed > 0 else 0.0

        self._detection_count += detections
        self._lost_tracks += lost_tracks
        self._last_time = now

    def get_metrics(self) -> Dict[str, Any]:
        """
        Return a snapshot of all current metrics.

        Returns:
            dict with keys:
                current_fps, avg_fps, runtime, detection_count, lost_tracks.
        """
        runtime = 0.0
        if self._start_time is not None and self._last_time is not None:
            runtime = self._last_time - self._start_time

        return {
            "current_fps": round(self._current_fps, 2),
            "avg_fps": round(self._avg_fps, 2),
            "runtime": round(runtime, 3),
            "detection_count": self._detection_count,
            "lost_tracks": self._lost_tracks,
        }

    def export(self, path: str) -> None:
        """
        Write the current metrics snapshot to a JSON file.

        Args:
            path: Filesystem path for the output JSON file.
        """
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.get_metrics(), fh, indent=2)
