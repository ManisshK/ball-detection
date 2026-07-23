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
_MIN_CIRCULARITY: float = 0.40


class BallDetector:
    """
    Detects round balls in a single BGR frame using HSV colour masking
    and contour circularity analysis.

    The HSV range used to build the mask can be overridden at runtime by
    setting the public attributes `_hsv_lower` and `_hsv_upper` (numpy
    uint8 arrays of shape (3,)).  When both are set, a single inclusive
    range is used instead of the default multi-range preset.

    No external model weights are required; the detector runs entirely
    with OpenCV and is suitable for real-time processing.
    """

    def __init__(self) -> None:
        """
        Initialise default HSV colour ranges and the morphological kernel.
        """
        # Default multi-band preset (used when no runtime override is set)
        self._default_hsv_ranges = [
            # Red – lower hue band (0-10)
            (np.array([0, 80, 80]),   np.array([10, 255, 255])),
            # Red – upper hue band (160-180)
            (np.array([160, 80, 80]), np.array([180, 255, 255])),
            # Orange / yellow
            (np.array([11, 80, 80]),  np.array([40, 255, 255])),
            # White / light-coloured balls
            (np.array([0, 0, 180]),   np.array([180, 40, 255])),
        ]

        # Runtime-overridable single HSV range (set by CameraController each tick).
        # None means "use the default preset above".
        self._hsv_lower: np.ndarray | None = None
        self._hsv_upper: np.ndarray | None = None

        # Runtime-overridable confidence threshold (set by CameraController each tick)
        self._confidence_threshold: float = CONFIDENCE_THRESHOLD

        # Runtime-overridable contour shape filters
        self._min_area: float = _MIN_AREA          # minimum contour area in px²
        self._aspect_ratio_tolerance: float = 0.4  # max deviation from 1:1 (0–1)

        # Runtime-overridable preprocessing kernel sizes
        self._morph_kernel_size: int = 5   # odd int; used for Open + Close kernels
        self._blur_kernel_size:  int = 5   # odd int; 0 or 1 disables Gaussian blur

        # Cache the last kernel size so we only rebuild the kernel when it changes
        self._cached_morph_k: int = 0
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
        Build a cleaned binary mask from the HSV image.

        Pipeline:
            1. HSV threshold  (user-defined range or default multi-band preset)
            2. Morphological Open  (removes isolated noise pixels)
            3. Morphological Close (fills gaps inside blobs)
            4. Gaussian Blur       (smooths blob edges; skipped when size < 2)

        All kernel sizes are read from runtime-overridable instance attributes
        so changes apply immediately on the next frame without restarting.

        Args:
            hsv: HSV image array.

        Returns:
            Binary mask (uint8, 0 or 255).
        """
        # 1. Colour threshold
        combined = np.zeros(hsv.shape[:2], dtype=np.uint8)
        if self._hsv_lower is not None and self._hsv_upper is not None:
            combined = cv2.inRange(hsv, self._hsv_lower, self._hsv_upper)
        else:
            for lo, hi in self._default_hsv_ranges:
                combined = cv2.bitwise_or(combined, cv2.inRange(hsv, lo, hi))

        # 2 & 3. Morphological Open → Close
        # Rebuild the kernel only when the size has changed (cheap guard)
        k = max(1, self._morph_kernel_size | 1)   # force odd, minimum 1
        if k != self._cached_morph_k:
            self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
            self._cached_morph_k = k

        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,  self._kernel)
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, self._kernel)

        # 4. Gaussian Blur (optional — skip when kernel size < 2)
        bk = max(1, self._blur_kernel_size | 1)   # force odd
        if bk >= 3:
            combined = cv2.GaussianBlur(combined, (bk, bk), 0)
            # Re-threshold to binary after blur
            _, combined = cv2.threshold(combined, 127, 255, cv2.THRESH_BINARY)

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
            # 1. Minimum area gate (runtime-configurable)
            if area < self._min_area or area > frame_area * _MAX_AREA_RATIO:
                continue

            perimeter = cv2.arcLength(contour, closed=True)
            if perimeter == 0:
                continue

            # 2. Circularity gate
            circularity = (4.0 * math.pi * area) / (perimeter ** 2)
            if circularity < _MIN_CIRCULARITY:
                continue

            # 3. Aspect-ratio gate — bounding-box w/h should be close to 1.0
            #    tolerance=0 means exact square (perfect circle projection),
            #    tolerance=1 means any aspect ratio is accepted.
            x, y, w, h = cv2.boundingRect(contour)
            if h > 0:
                aspect = w / h
                # deviation from 1:1; 0 = perfect, grows as shape becomes elongated
                deviation = abs(1.0 - aspect)
                if deviation > self._aspect_ratio_tolerance:
                    continue

            # Normalised area score: small balls get lower confidence
            area_score = min(area / reference_area, 1.0)
            confidence = round(circularity * area_score, 4)

            # 4. Confidence gate
            if confidence < self._confidence_threshold:
                continue

            detections.append({
                "bbox": [x, y, x + w, y + h],
                "confidence": confidence,
            })

        return detections
