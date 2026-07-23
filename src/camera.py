"""
camera.py - Webcam capture management using OpenCV.
"""

from typing import Tuple

import cv2
import numpy as np

from config import CAMERA_INDEX, FRAME_HEIGHT, FRAME_WIDTH


class CameraManager:
    """Manages webcam initialisation, frame capture, and release."""

    def __init__(self) -> None:
        """Initialise internal state; camera is opened lazily via start()."""
        self._cap: cv2.VideoCapture | None = None

    def start(self) -> bool:
        """
        Open the webcam and configure resolution.
        """

        self._cap = cv2.VideoCapture(CAMERA_INDEX)

        self._cap.set(cv2.CAP_PROP_FPS, 60)

        print("FPS:", self._cap.get(cv2.CAP_PROP_FPS))
        print(
            "Resolution:",
            self._cap.get(cv2.CAP_PROP_FRAME_WIDTH),
            "x",
            self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
        )

        if not self._cap.isOpened():
            self._cap = None
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)

        return True

    def read(self) -> Tuple[bool, np.ndarray | None]:
        """
        Capture a single frame from the webcam.

        Returns:
            (success, frame) where success is a bool and frame is a BGR
            numpy array, or None if the camera is not open.
        """
        if self._cap is None or not self._cap.isOpened():
            return False, None

        success, frame = self._cap.read()
        return success, frame if success else None

    def release(self) -> None:
        """Release the camera resource and reset internal state."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None