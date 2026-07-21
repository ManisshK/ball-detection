"""
visualization.py - OpenCV overlay rendering for ball detection and tracking.
"""

from collections import deque
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


# -- colour palette for distinct track IDs (BGR) --
_PALETTE: List[Tuple[int, int, int]] = [
    (0, 255, 0),
    (255, 128, 0),
    (0, 128, 255),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 0),
    (128, 0, 255),
    (0, 200, 100),
]

_FONT = cv2.FONT_HERSHEY_SIMPLEX


def _track_color(track_id: int) -> Tuple[int, int, int]:
    """Return a consistent BGR colour for a given track ID."""
    return _PALETTE[track_id % len(_PALETTE)]


class Visualizer:
    """Draws detection and tracking overlays onto OpenCV frames."""

    def __init__(
        self,
        bbox_thickness: int = 2,
        text_scale: float = 0.55,
        text_thickness: int = 1,
        trajectory_thickness: int = 2,
    ) -> None:
        """
        Args:
            bbox_thickness:       Line thickness for bounding boxes.
            text_scale:           Font scale for all text overlays.
            text_thickness:       Line thickness for text.
            trajectory_thickness: Line thickness for trajectory trails.
        """
        self._bbox_thickness = bbox_thickness
        self._text_scale = text_scale
        self._text_thickness = text_thickness
        self._traj_thickness = trajectory_thickness

    # ------------------------------------------------------------------
    # Per-detection drawing helpers
    # ------------------------------------------------------------------

    def draw_bbox(
        self,
        frame: np.ndarray,
        bbox: Tuple[int, int, int, int],
        track_id: int,
    ) -> None:
        """
        Draw a coloured bounding box on *frame*.

        Args:
            frame:    BGR image array (modified in-place).
            bbox:     (x1, y1, x2, y2) in pixels.
            track_id: Track identifier used to pick a consistent colour.
        """
        x1, y1, x2, y2 = bbox
        color = _track_color(track_id)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, self._bbox_thickness)

    def draw_track_id(
        self,
        frame: np.ndarray,
        track_id: int,
        position: Tuple[int, int],
    ) -> None:
        """
        Draw the track ID label above a bounding box.

        Args:
            frame:    BGR image array (modified in-place).
            track_id: Integer track ID to display.
            position: (x, y) pixel coordinate for the label origin.
        """
        color = _track_color(track_id)
        label = f"ID:{track_id}"
        cv2.putText(
            frame, label, position, _FONT,
            self._text_scale, color, self._text_thickness, cv2.LINE_AA,
        )

    def draw_speed(
        self,
        frame: np.ndarray,
        track_id: int,
        speed: float,
        position: Tuple[int, int],
    ) -> None:
        """
        Draw the speed value (px/s) for a tracked ball.

        Args:
            frame:    BGR image array (modified in-place).
            track_id: Used to pick a consistent label colour.
            speed:    Speed in pixels per second.
            position: (x, y) pixel coordinate for the text origin.
        """
        color = _track_color(track_id)
        label = f"{speed:.1f} px/s"
        cv2.putText(
            frame, label, position, _FONT,
            self._text_scale, color, self._text_thickness, cv2.LINE_AA,
        )

    def draw_trajectory(
        self,
        frame: np.ndarray,
        track_id: int,
        trajectory: deque,
    ) -> None:
        """
        Draw a fading polyline trail from the trajectory history.

        Older segments are drawn more transparently by blending with the
        original frame using decreasing alpha weights.

        Args:
            frame:      BGR image array (modified in-place).
            track_id:   Used to pick a consistent trail colour.
            trajectory: deque of (x, y) tuples, oldest first.
        """
        pts = list(trajectory)
        if len(pts) < 2:
            return

        color = _track_color(track_id)
        n = len(pts)

        for i in range(1, n):
            alpha = i / n  # 0 → transparent (old) … 1 → opaque (new)
            pt1 = (int(pts[i - 1][0]), int(pts[i - 1][1]))
            pt2 = (int(pts[i][0]), int(pts[i][1]))

            # Blend the segment onto the frame for a fade effect
            overlay = frame.copy()
            cv2.line(overlay, pt1, pt2, color, self._traj_thickness, cv2.LINE_AA)
            cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    # ------------------------------------------------------------------
    # Global HUD helpers
    # ------------------------------------------------------------------

    def draw_fps(
        self,
        frame: np.ndarray,
        fps: float,
        position: Tuple[int, int] = (10, 25),
    ) -> None:
        """
        Draw the current FPS counter in the top-left corner.

        Args:
            frame:    BGR image array (modified in-place).
            fps:      Frames per second value to display.
            position: (x, y) pixel coordinate for the text origin.
        """
        label = f"FPS: {fps:.1f}"
        cv2.putText(
            frame, label, position, _FONT,
            self._text_scale, (200, 200, 200), self._text_thickness, cv2.LINE_AA,
        )

    def draw_mode(
        self,
        frame: np.ndarray,
        mode: str,
        position: Optional[Tuple[int, int]] = None,
    ) -> None:
        """
        Draw the current operating mode label (e.g. 'TRACKING', 'PAUSED').

        Args:
            frame:    BGR image array (modified in-place).
            mode:     Mode string to display.
            position: (x, y) pixel coordinate; defaults to top-right area.
        """
        if position is None:
            h, w = frame.shape[:2]
            # Estimate text width to right-align
            (tw, _), _ = cv2.getTextSize(
                mode, _FONT, self._text_scale, self._text_thickness
            )
            position = (w - tw - 10, 25)

        cv2.putText(
            frame, mode, position, _FONT,
            self._text_scale, (0, 220, 255), self._text_thickness, cv2.LINE_AA,
        )

    # ------------------------------------------------------------------
    # Composite render
    # ------------------------------------------------------------------

    def render(
        self,
        frame: np.ndarray,
        tracks: List[Dict],
        speeds: Optional[Dict[int, float]] = None,
        trajectories: Optional[Dict[int, deque]] = None,
        fps: Optional[float] = None,
        mode: Optional[str] = None,
    ) -> np.ndarray:
        """
        Draw all overlays for a single frame and return it.

        Args:
            frame:        BGR image array (modified in-place and returned).
            tracks:       List of track dicts, each with keys:
                            - 'id'     (int)
                            - 'bbox'   (x1, y1, x2, y2)
                            - 'center' (x, y)
            speeds:       Optional map of track_id -> speed (px/s).
            trajectories: Optional map of track_id -> trajectory deque.
            fps:          Optional current FPS to display.
            mode:         Optional mode label to display.

        Returns:
            The annotated frame (same array that was passed in).
        """
        # Draw trajectories first (below other overlays)
        if trajectories:
            for track in tracks:
                tid = track["id"]
                traj = trajectories.get(tid)
                if traj:
                    self.draw_trajectory(frame, tid, traj)

        # Draw per-track overlays
        for track in tracks:
            tid = track["id"]
            bbox = track.get("bbox")
            center = track.get("center")

            if bbox:
                self.draw_bbox(frame, bbox, tid)
                x1, y1 = bbox[0], bbox[1]
                self.draw_track_id(frame, tid, (x1, max(y1 - 5, 10)))

            if center and speeds:
                spd = speeds.get(tid, 0.0)
                cx, cy = int(center[0]), int(center[1])
                self.draw_speed(frame, tid, spd, (cx + 6, cy - 6))

        # HUD
        if fps is not None:
            self.draw_fps(frame, fps)

        if mode:
            self.draw_mode(frame, mode)

        return frame
