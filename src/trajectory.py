"""
trajectory.py - Manages per-ball trajectory history using deque-based storage.
"""

from collections import defaultdict, deque
from typing import Dict, Optional, Tuple


class TrajectoryManager:
    """Stores and manages trajectory points for multiple tracked balls."""

    def __init__(self, max_length: int = 30) -> None:
        """
        Initialize the TrajectoryManager.

        Args:
            max_length: Maximum number of trajectory points to retain per track.
        """
        self._max_length = max_length
        self._trajectories: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=self._max_length)
        )

    def update(self, track_id: int, center: Tuple[int, int]) -> None:
        """
        Append a new center point to the trajectory of the given track.

        Args:
            track_id: Unique identifier for the tracked ball.
            center: (x, y) pixel coordinates of the ball center.
        """
        self._trajectories[track_id].append(center)

    def get_trajectory(self, track_id: int) -> Optional[deque]:
        """
        Retrieve the trajectory deque for a given track.

        Args:
            track_id: Unique identifier for the tracked ball.

        Returns:
            A deque of (x, y) tuples, or None if the track does not exist.
        """
        return self._trajectories.get(track_id)

    def clear(self, track_id: int) -> None:
        """
        Remove all trajectory data for the given track.

        Args:
            track_id: Unique identifier for the tracked ball.
        """
        self._trajectories.pop(track_id, None)
