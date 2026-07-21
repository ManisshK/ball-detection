"""
speed.py - Estimates per-ball speed in pixels per second with EMA smoothing.
"""

import math
from typing import Dict, Optional, Tuple


class SpeedEstimator:
    """
    Computes smoothed speed (px/s) for multiple tracked balls using
    exponential moving average (EMA).
    """

    def __init__(self, smoothing_factor: float = 0.7) -> None:
        """
        Initialize the SpeedEstimator.

        Args:
            smoothing_factor: EMA weight for the previous speed (0 < alpha < 1).
                              Higher values retain more history; lower values
                              react faster to changes.
        """
        self._alpha = smoothing_factor
        # Maps track_id -> (last_center, last_timestamp)
        self._prev: Dict[int, Tuple[Tuple[float, float], float]] = {}
        # Maps track_id -> smoothed speed (px/s)
        self._speeds: Dict[int, float] = {}

    def update(
        self,
        track_id: int,
        center: Tuple[float, float],
        timestamp: float,
    ) -> None:
        """
        Update the speed estimate for a tracked ball.

        Args:
            track_id:  Unique identifier for the tracked ball.
            center:    Current (x, y) position in pixels.
            timestamp: Current time in seconds (e.g. time.time()).
        """
        if track_id in self._prev:
            prev_center, prev_ts = self._prev[track_id]
            dt = timestamp - prev_ts

            if dt > 0:
                dx = center[0] - prev_center[0]
                dy = center[1] - prev_center[1]
                current_speed = math.sqrt(dx * dx + dy * dy) / dt

                previous_speed = self._speeds.get(track_id, current_speed)
                self._speeds[track_id] = (
                    self._alpha * previous_speed
                    + (1.0 - self._alpha) * current_speed
                )
            # If dt <= 0 (duplicate or out-of-order timestamp), skip update

        self._prev[track_id] = (center, timestamp)

    def get_speed(self, track_id: int) -> float:
        """
        Return the current smoothed speed for a tracked ball.

        Args:
            track_id: Unique identifier for the tracked ball.

        Returns:
            Smoothed speed in pixels per second, or 0.0 if insufficient data.
        """
        return self._speeds.get(track_id, 0.0)

    def clear(self, track_id: int) -> None:
        """
        Remove all speed state for the given track.

        Args:
            track_id: Unique identifier for the tracked ball.
        """
        self._prev.pop(track_id, None)
        self._speeds.pop(track_id, None)
