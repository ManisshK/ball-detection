"""
detector.py - Colour and shape-based ball detector using OpenCV.

Detection pipeline:
  1. Convert frame to HSV colour space.
  2. Threshold for typical ball colours (red, orange, yellow, white).
  3. Morphologically clean the mask.
  4. Find contours and filter by circularity.
  5. Compute a confidence score from circularity × normalised area.
  6. Discard detections below CONFIDENCE_THRESHOLD.
"""

import math
from typing import Any, Dict, List

import cv2
import numpy as np

from config import CONFIDENCE_THRESHOLD

# Minimum contour area in pixels² to consider (filters out noise)
_MIN_AREA: float = 200.0
# Maximum fraction of the frame area a ball may occupy
_MAX_AREA_RATIO: float = 0.30
# Circularity threshold: 1.0 = perfect circle; balls are typically > 0.65
_MIN_CIRCULARITY: float = 0.65


class BallDetector:
    """
    Detects round balls in a single BGR frame using HSV colour masking
    and contour circularity analysis.

    No external model weights are required; the detector runs entirely
    with OpenCV and is suitable for real-time processing.
    """

    def __init__(self) -> None:
        """
        Precompute the HSV colour ranges and morphological kernel once
        so they are reused across every detect() call.
        """
        # HSV ranges that cover common ball colours:
        # red (wraps hue), orange, yellow, and white
        self._hsv_ranges = [
            # Red – lower hue band (0-10)
            (np.array([0, 80, 80]),   np.array([10, 255, 255])),
            # Red – upper hue band (160-180)
            (np.array([160, 80, 80]), np.array([180, 255, 255])),
            # Orange / yellow
            (np.array([11, 80, 80]),  np.array([40, 255, 255])),
            # White / light-coloured balls
            (np.array([0, 0, 180]),   np.array([180, 40, 255])),
        ]

        # 5×5 elliptical kernel for morphological noise removal
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect balls in a single BGR frame.

        Args:
            frame: BGR image as a numpy array (H × W × 3).

        Returns:
            List of detection dicts, each with:
                {
                    "bbox":       [x1, y1, x2, y2],   # int pixel coords
                    "confidence": float                 # 0.0 – 1.0
                }
            Only detections with confidence >= CONFIDENCE_THRESHOLD are
            returned.  The list may be empty.
        """
        if frame is None or frame.size == 0:
            return []

        frame_area = frame.shape[0] * frame.shape[1]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = self._build_mask(hsv)
        return self._extract_detections(mask, frame_area)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_mask(self, hsv: np.ndarray) -> np.ndarray:
        """
        Combine all HSV colour ranges into a single cleaned binary mask.

        Args:
            hsv: HSV image array.

        Returns:
            Binary mask (uint8, 0 or 255).
        """
        combined = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in self._hsv_ranges:
            combined = cv2.bitwise_or(combined, cv2.inRange(hsv, lo, hi))

        # Morphological open removes small noise; close fills gaps inside blobs
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,  self._kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, self._kernel)
        return combined

    def _extract_detections(
        self,
        mask: np.ndarray,
        frame_area: int,
    ) -> List[Dict[str, Any]]:
        """
        Find contours in the mask and return ball detections.

        Confidence is defined as:
            circularity × clamp(area / reference_area, 0, 1)
        where reference_area is 5 % of the frame area, so a mid-sized
        ball at typical game distance scores near 1.0.

        Args:
            mask:       Binary mask from _build_mask().
            frame_area: Total pixel area of the source frame.

        Returns:
            Filtered list of detection dicts.
        """
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        detections: List[Dict[str, Any]] = []
        reference_area = frame_area * 0.05  # 5 % of frame = "full confidence" size

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < _MIN_AREA or area > frame_area * _MAX_AREA_RATIO:
                continue

            perimeter = cv2.arcLength(contour, closed=True)
            if perimeter == 0:
                continue

            circularity = (4.0 * math.pi * area) / (perimeter ** 2)
            if circularity < _MIN_CIRCULARITY:
                continue

            # Normalised area score: small balls get lower confidence
            area_score = min(area / reference_area, 1.0)
            confidence = round(circularity * area_score, 4)

            if confidence < CONFIDENCE_THRESHOLD:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            detections.append({
                "bbox": [x, y, x + w, y + h],
                "confidence": confidence,
            })

        return detections
