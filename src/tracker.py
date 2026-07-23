"""
tracker.py - IoU-based multi-ball tracker with age-based track eviction.

Algorithm:
  1. Compute IoU between every active track and every new detection.
  2. Greedily match detections to tracks (highest IoU first).
  3. Unmatched detections spawn new tracks.
  4. Unmatched tracks increment their miss counter; tracks that exceed
     MAX_TRACK_AGE consecutive misses are removed.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from config import MAX_TRACK_AGE

# IoU threshold below which a detection is not considered a match
_IOU_THRESHOLD: float = 0.25


def _center(bbox: List[int]) -> Tuple[int, int]:
    """Return the (x, y) centre pixel of a bounding box [x1, y1, x2, y2]."""
    return ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)


def _iou(a: List[int], b: List[int]) -> float:
    """
    Compute Intersection-over-Union for two bounding boxes.

    Args:
        a, b: Each is [x1, y1, x2, y2].

    Returns:
        IoU score in [0.0, 1.0].
    """
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])

    inter_w = max(0, ix2 - ix1)
    inter_h = max(0, iy2 - iy1)
    inter = inter_w * inter_h

    if inter == 0:
        return 0.0

    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class _Track:
    """Internal representation of a single tracked ball."""

    __slots__ = ("id", "bbox", "misses", "timestamp")

    def __init__(self, track_id: int, bbox: List[int]) -> None:
        self.id: int = track_id
        self.bbox: List[int] = bbox
        self.misses: int = 0
        self.timestamp: float = time.time()

    def update(self, bbox: List[int]) -> None:
        """Refresh the track with a new matched detection."""
        self.bbox = bbox
        self.misses = 0
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to the public track format."""
        return {
            "id": self.id,
            "bbox": self.bbox,
            "center": _center(self.bbox),
            "timestamp": self.timestamp,
        }


class BallTracker:
    """
    Tracks multiple balls across frames using IoU-based association.

    Tracks are assigned unique integer IDs that persist as long as the
    ball remains visible.  A track is dropped after MAX_TRACK_AGE
    consecutive frames with no matching detection.
    """

    def __init__(self) -> None:
        """Initialise the tracker with no active tracks."""
        self._tracks: List[_Track] = []
        self._next_id: int = 1

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(self, detections: List[Dict[str, Any]]) -> None:
        """
        Associate new detections with existing tracks and update state.

        Args:
            detections: List of dicts with keys 'bbox' ([x1,y1,x2,y2])
                        and 'confidence' (float), as returned by BallDetector.
        """
        unmatched_det_indices = list(range(len(detections)))

        # --- Match detections to existing tracks via IoU ---
        if self._tracks and detections:
            # Build IoU matrix: rows = tracks, cols = detections
            iou_matrix = [
                [_iou(track.bbox, det["bbox"]) for det in detections]
                for track in self._tracks
            ]

            matched_track_indices = set()

            # Greedy match: pick highest IoU pair repeatedly
            while True:
                best_iou = _IOU_THRESHOLD
                best_t: Optional[int] = None
                best_d: Optional[int] = None

                for t_idx, row in enumerate(iou_matrix):
                    if t_idx in matched_track_indices:
                        continue
                    for d_idx, score in enumerate(row):
                        if d_idx not in unmatched_det_indices:
                            continue
                        if score > best_iou:
                            best_iou = score
                            best_t = t_idx
                            best_d = d_idx

                if best_t is None:
                    break

                self._tracks[best_t].update(detections[best_d]["bbox"])
                matched_track_indices.add(best_t)
                unmatched_det_indices.remove(best_d)

            # Increment miss counter for unmatched tracks
            for t_idx, track in enumerate(self._tracks):
                if t_idx not in matched_track_indices:
                    track.misses += 1
        else:
            # No tracks yet, or no detections — all existing tracks missed
            for track in self._tracks:
                track.misses += 1

        # --- Spawn new tracks for unmatched detections ---
        for d_idx in unmatched_det_indices:
            self._tracks.append(_Track(self._next_id, detections[d_idx]["bbox"]))
            self._next_id += 1

        # --- Evict stale tracks ---
        self._tracks = [t for t in self._tracks if t.misses <= MAX_TRACK_AGE]

    def get_tracks(self) -> List[Dict[str, Any]]:
        """
        Return all currently active tracks.

        Returns:
            List of track dicts, each containing:
                {
                    "id":        int,
                    "bbox":      [x1, y1, x2, y2],
                    "center":    (x, y),
                    "timestamp": float
                }
        """
        return [t.to_dict() for t in self._tracks]

    def clear(self) -> None:
        """Remove all active tracks and reset the ID counter."""
        self._tracks.clear()
        self._next_id = 1
