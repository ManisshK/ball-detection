"""
controller.py - Full detection/tracking pipeline controller for the PySide6 UI.

Per-frame pipeline (runs on QTimer, main thread):
    CameraManager.read()
        -> BallDetector.detect()
        -> BallTracker.update()
        -> TrajectoryManager.update()  / SpeedEstimator.update()
        -> Visualizer.render()         (bbox, track-ID, trajectory, FPS, mode)
        -> BGR ndarray -> QPixmap      (emitted to FeedWidget)

No cv2.imshow() is used anywhere in this file.
No backend files are modified.
"""

import json
import os
import sys
import time
from typing import Optional, Tuple

# ── make src/ importable without touching any backend file ───────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2
import numpy as np

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap

from camera import CameraManager
from config import MAX_TRAJECTORY_LENGTH
from detector import BallDetector
from metrics import MetricsManager
from report import ReportGenerator
from speed import SpeedEstimator
from tracker import BallTracker
from trajectory import TrajectoryManager
from visualization import Visualizer


# ── Video recorder ────────────────────────────────────────────────────────────

class VideoRecorder:
    """
    Wraps cv2.VideoWriter to record annotated BGR frames to disk.

    Usage:
        recorder.start(width, height, fps, output_dir)
        recorder.write(bgr_frame)   # called each pipeline tick
        info = recorder.stop()      # returns metadata dict
    """

    _FOURCC = cv2.VideoWriter_fourcc(*"mp4v")  # .mp4 container

    def __init__(self) -> None:
        self._writer: cv2.VideoWriter | None = None
        self._path:   str   = ""
        self._width:  int   = 0
        self._height: int   = 0
        self._fps:    float = 30.0
        self._frames: int   = 0
        self._start_ts: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self._writer is not None

    def start(
        self,
        width: int,
        height: int,
        fps: float,
        output_dir: str,
    ) -> str:
        """
        Open a new VideoWriter.

        Args:
            width, height: Frame dimensions in pixels.
            fps:           Target playback frame rate.
            output_dir:    Folder to write the video into.

        Returns:
            Absolute path of the output file.
        """
        if self._writer is not None:
            return self._path   # already recording

        os.makedirs(output_dir, exist_ok=True)
        stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{stamp}.mp4"
        self._path   = os.path.abspath(os.path.join(output_dir, filename))
        self._width  = width
        self._height = height
        self._fps    = max(fps, 1.0)
        self._frames = 0
        self._start_ts = time.time()

        self._writer = cv2.VideoWriter(
            self._path, self._FOURCC, self._fps, (self._width, self._height)
        )
        return self._path

    def write(self, frame: np.ndarray) -> None:
        """Write one annotated BGR frame."""
        if self._writer is None:
            return
        # Resize if the frame doesn't match the writer dimensions (safety guard)
        h, w = frame.shape[:2]
        if w != self._width or h != self._height:
            frame = cv2.resize(frame, (self._width, self._height))
        self._writer.write(frame)
        self._frames += 1

    def stop(self) -> dict:
        """
        Finalise and release the VideoWriter.

        Returns:
            dict with keys: path, filename, duration_s, width, height,
                            avg_fps, frame_count.
        """
        if self._writer is None:
            return {}
        self._writer.release()
        self._writer = None

        elapsed = max(time.time() - self._start_ts, 0.001)
        info = {
            "path":       self._path,
            "filename":   os.path.basename(self._path),
            "duration_s": round(elapsed, 2),
            "width":      self._width,
            "height":     self._height,
            "avg_fps":    round(self._frames / elapsed, 1),
            "frame_count": self._frames,
        }
        self._path = ""
        return info

    def release(self) -> None:
        """Safe cleanup — call on application close."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None


# ── Runtime configuration (mutable, read by the pipeline every tick) ─────────

class RuntimeConfig:
    """
    Holds all user-configurable values that can change while the app is running.
    The pipeline reads these attributes on every frame — changes apply instantly
    for display settings, and on the next Start press for camera settings.

    Persistence:
        Settings are saved to `outputs/settings.json` automatically whenever
        any attribute is updated.  On startup the file is loaded so the last
        session's values are restored.  If the file does not exist the
        hardcoded defaults are used.
    """

    RESOLUTIONS: dict = {
        "640×480":   (640,  480),
        "1280×720":  (1280, 720),
        "1920×1080": (1920, 1080),
    }

    # Path where settings are persisted (relative to the project root)
    _SETTINGS_PATH: str = os.path.join("outputs", "settings.json")

    # Names of attributes that are persisted (excludes class-level constants)
    _PERSIST_KEYS: tuple = (
        "camera_index", "frame_width", "frame_height",
        "show_fps", "show_trajectory", "show_hsv_mask",
        "confidence_threshold",
        "hsv_hue_min", "hsv_hue_max",
        "hsv_sat_min", "hsv_sat_max",
        "hsv_val_min", "hsv_val_max",
        "min_area", "aspect_ratio_tolerance",
        "morph_kernel_size", "blur_kernel_size",
        "single_ball_mode",
    )

    def __init__(self) -> None:
        import config as _c
        # Bypass __setattr__ during construction so we don't trigger saves
        # before all fields exist.  Use object.__setattr__ directly.
        _set = object.__setattr__

        _set(self, "camera_index",           _c.CAMERA_INDEX)
        _set(self, "frame_width",            _c.FRAME_WIDTH)
        _set(self, "frame_height",           _c.FRAME_HEIGHT)
        _set(self, "show_fps",               _c.SHOW_FPS)
        _set(self, "show_trajectory",        True)
        _set(self, "show_hsv_mask",          False)
        _set(self, "confidence_threshold",   _c.CONFIDENCE_THRESHOLD)
        _set(self, "hsv_hue_min",            0)
        _set(self, "hsv_hue_max",            180)
        _set(self, "hsv_sat_min",            60)
        _set(self, "hsv_sat_max",            255)
        _set(self, "hsv_val_min",            60)
        _set(self, "hsv_val_max",            255)
        _set(self, "min_area",               200)
        _set(self, "aspect_ratio_tolerance", 0.4)
        _set(self, "morph_kernel_size",      5)
        _set(self, "blur_kernel_size",       5)
        _set(self, "single_ball_mode",       False)

        # Load persisted values on top of defaults (silently ignored if missing)
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def __setattr__(self, name: str, value) -> None:
        """Set attribute and auto-save whenever a persisted key changes."""
        object.__setattr__(self, name, value)
        if name in self._PERSIST_KEYS:
            self._save()

    def _save(self) -> None:
        """Write all persisted settings to JSON (silently ignores I/O errors)."""
        try:
            os.makedirs(os.path.dirname(self._SETTINGS_PATH), exist_ok=True)
            data = {k: getattr(self, k) for k in self._PERSIST_KEYS}
            with open(self._SETTINGS_PATH, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
        except OSError:
            pass  # non-fatal — run without persistence if the path is unavailable

    def _load(self) -> None:
        """
        Load settings from JSON, applying only keys that exist in _PERSIST_KEYS.
        Unknown keys and type errors are silently ignored so a corrupted file
        never prevents startup.
        """
        if not os.path.isfile(self._SETTINGS_PATH):
            return
        try:
            with open(self._SETTINGS_PATH, "r", encoding="utf-8") as fh:
                data: dict = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return

        for key in self._PERSIST_KEYS:
            if key not in data:
                continue
            try:
                # Cast to the same type as the current default to guard against
                # a stale JSON containing a string where an int is expected.
                current = getattr(self, key)
                value   = type(current)(data[key])
                object.__setattr__(self, key, value)
            except (TypeError, ValueError):
                pass  # keep the default if the stored value is unusable


class CameraController(QObject):
    """
    Drives the real-time detection/tracking pipeline and delivers annotated
    frames to the UI via Qt signals.

    Signals:
        frame_ready(QPixmap)  – annotated frame, ready to display.
        camera_online(bool)   – camera state changed.
        error(str)            – human-readable failure message.
        stats_updated(dict)   – per-frame stats for the right-panel cards.
    """

    frame_ready   = Signal(QPixmap)
    camera_online = Signal(bool)
    error         = Signal(str)
    stats_updated = Signal(dict)   # keys: fps, detections, track_id, speed, confidence
    mask_ready    = Signal(QPixmap)  # binary HSV mask; only emitted when show_hsv_mask=True

    _INTERVAL_MS: int = 33         # ~30 fps

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        # ── runtime config (shared with SettingsPage) ─────────────────────────
        self._cfg = RuntimeConfig()
        self.config = self._cfg

        # ── backend objects ───────────────────────────────────────────────────
        self._camera      = CameraManager()
        self._detector    = BallDetector()
        self._tracker     = BallTracker()
        self._trajectories = TrajectoryManager(max_length=MAX_TRAJECTORY_LENGTH)
        self._speed_est   = SpeedEstimator()
        self._visualizer  = Visualizer()
        self._metrics     = MetricsManager()
        self._reporter    = ReportGenerator()   # reuse the existing backend class

        # ── session accumulators ──────────────────────────────────────────────
        self._prev_track_ids: set  = set()
        self._max_fps:   float     = 0.0
        self._max_speed: float     = 0.0
        self._tracks_created: int  = 0

        self._running = False

        # Holds the most-recent annotated QPixmap so Capture Frame can grab it
        self._last_pixmap: Optional[QPixmap] = None

        # Video recorder
        self._recorder = VideoRecorder()

        self._timer = QTimer(self)
        self._timer.setInterval(self._INTERVAL_MS)
        self._timer.timeout.connect(self._process_frame)

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Open the camera and start the pipeline timer."""
        if self._running:
            return

        # Reset session state
        self._tracker.clear()
        self._prev_track_ids  = set()
        self._max_fps         = 0.0
        self._max_speed       = 0.0
        self._tracks_created  = 0
        self._metrics         = MetricsManager()

        # Push RuntimeConfig values into the config module so CameraManager
        # picks up any user-changed camera index / resolution on this start.
        import config as _cfg_mod
        _cfg_mod.CAMERA_INDEX  = self.config.camera_index
        _cfg_mod.FRAME_WIDTH   = self.config.frame_width
        _cfg_mod.FRAME_HEIGHT  = self.config.frame_height

        if not self._camera.start():
            self.error.emit("Camera Not Available")
            self.camera_online.emit(False)
            return

        self._running = True
        self.camera_online.emit(True)
        self._timer.start()

    def stop(self) -> None:
        """Stop the pipeline and release the camera."""
        if not self._running:
            return
        self._timer.stop()
        self._recorder.release()   # stop any active recording cleanly
        self._camera.release()
        self._running = False
        self.camera_online.emit(False)

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Recording API ─────────────────────────────────────────────────────────

    def start_recording(self, output_dir: str = os.path.join("outputs", "videos")) -> str:
        """
        Begin recording annotated frames to an MP4 file.

        Returns:
            Absolute path of the output file (available immediately).
        """
        w = self._cfg.frame_width
        h = self._cfg.frame_height
        fps = self._metrics.get_metrics().get("avg_fps", 0.0)
        fps = fps if fps >= 1.0 else 30.0
        return self._recorder.start(w, h, fps, output_dir)

    def stop_recording(self) -> dict:
        """
        Stop recording and finalise the file.

        Returns:
            Metadata dict from VideoRecorder.stop().
        """
        return self._recorder.stop()

    @property
    def is_recording(self) -> bool:
        return self._recorder.is_recording

    # ── Report / capture API ──────────────────────────────────────────────────

    def export_session(self) -> Tuple[str, str]:
        """
        Generate the session report using current backend data and save both
        JSON and TXT files.  Reuses ReportGenerator — no logic is duplicated.

        Returns:
            (json_path, txt_path) absolute paths of the written files.
        """
        avg_spd = self._avg_speed()
        self._reporter.generate(
            metrics=self._metrics.get_metrics(),
            max_fps=self._max_fps,
            avg_ball_speed=avg_spd,
            tracks_created=self._tracks_created,
        )
        json_path = self._reporter.save_json()
        txt_path  = self._reporter.save_text()
        return json_path, txt_path

    @property
    def json_report_path(self) -> str:
        """Absolute path where the JSON report is (or will be) written."""
        return os.path.abspath(
            os.path.join("outputs", "reports", "session_report.json")
        )

    @property
    def txt_report_path(self) -> str:
        """Absolute path where the TXT report is (or will be) written."""
        return os.path.abspath(
            os.path.join("outputs", "reports", "session_report.txt")
        )

    @property
    def last_pixmap(self) -> Optional[QPixmap]:
        """The most-recently rendered annotated frame, or None."""
        return self._last_pixmap

    def get_session_summary(self) -> dict:
        """
        Return a snapshot of all session statistics at the moment of stopping.

        Intended to be called immediately after stop() so the final metrics
        are captured before the next session resets the counters.

        Returns:
            dict with keys:
                runtime_s, current_fps, avg_fps, max_fps,
                detection_count, tracks_created, lost_tracks,
                avg_speed, max_speed,
                json_report_path, txt_report_path.
        """
        m = self._metrics.get_metrics()
        return {
            "runtime_s":       m.get("runtime", 0.0),
            "current_fps":     m.get("current_fps", 0.0),
            "avg_fps":         m.get("avg_fps", 0.0),
            "max_fps":         self._max_fps,
            "detection_count": m.get("detection_count", 0),
            "tracks_created":  self._tracks_created,
            "lost_tracks":     m.get("lost_tracks", 0),
            "avg_speed":       self._avg_speed(),
            "max_speed":       self._max_speed,
            "json_report_path": self.json_report_path,
            "txt_report_path":  self.txt_report_path,
        }

    def _avg_speed(self) -> float:
        """Mean speed across all currently tracked balls (px/s)."""
        track_ids = [t["id"] for t in self._tracker.get_tracks()]
        if not track_ids:
            return 0.0
        speeds = [self._speed_est.get_speed(tid) for tid in track_ids]
        return sum(speeds) / len(speeds)

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _process_frame(self) -> None:
        """Single pipeline tick: read → detect → track → visualize → emit."""
        frame_ts = time.time()

        # 1. Capture
        success, frame = self._camera.read()
        if not success or frame is None:
            self.stop()
            self.error.emit("Camera Not Available")
            return

        # 2. Detect — push live config values into the detector before each call
        self._detector._confidence_threshold  = self._cfg.confidence_threshold
        self._detector._min_area              = self._cfg.min_area
        self._detector._aspect_ratio_tolerance = self._cfg.aspect_ratio_tolerance
        self._detector._morph_kernel_size      = self._cfg.morph_kernel_size
        self._detector._blur_kernel_size       = self._cfg.blur_kernel_size
        self._detector._hsv_lower = np.array([
            self._cfg.hsv_hue_min,
            self._cfg.hsv_sat_min,
            self._cfg.hsv_val_min,
        ], dtype=np.uint8)
        self._detector._hsv_upper = np.array([
            self._cfg.hsv_hue_max,
            self._cfg.hsv_sat_max,
            self._cfg.hsv_val_max,
        ], dtype=np.uint8)
        detections = self._detector.detect(frame)

        # Emit the HSV mask for debug visualisation when requested
        if self._cfg.show_hsv_mask:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = self._detector._build_mask(hsv)
            # Convert single-channel mask to a 3-channel BGR image for display
            mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            self.mask_ready.emit(self._bgr_to_pixmap(mask_bgr))

        # Single Ball Mode — sort by confidence desc, keep only the best one
        if detections:
            detections = sorted(detections, key=lambda d: d["confidence"], reverse=True)
            if self._cfg.single_ball_mode:
                detections = detections[:1]

        # 3. Track
        prev_ids = {t["id"] for t in self._tracker.get_tracks()}
        self._tracker.update(detections)
        current_tracks = self._tracker.get_tracks()
        current_ids    = {t["id"] for t in current_tracks}

        new_ids   = current_ids - prev_ids
        lost_ids  = prev_ids - current_ids
        self._tracks_created += len(new_ids)

        # 4. Trajectory + speed
        for track in current_tracks:
            tid    = track["id"]
            center = track["center"]
            self._trajectories.update(tid, center)
            self._speed_est.update(tid, center, frame_ts)

        for lost_id in lost_ids:
            self._trajectories.clear(lost_id)
            self._speed_est.clear(lost_id)

        # 5. Metrics
        self._metrics.update(
            detections=len(detections),
            lost_tracks=len(lost_ids),
            timestamp=frame_ts,
        )
        m           = self._metrics.get_metrics()
        current_fps = m["current_fps"]
        if current_fps > self._max_fps:
            self._max_fps = current_fps

        # 6. Build overlay helpers — respect show_trajectory setting
        traj_map = {}
        if self._cfg.show_trajectory:
            traj_map = {
                t["id"]: self._trajectories.get_trajectory(t["id"])
                for t in current_tracks
                if self._trajectories.get_trajectory(t["id"]) is not None
            }
        speeds_map = {t["id"]: self._speed_est.get_speed(t["id"])
                      for t in current_tracks}
        if speeds_map:
            frame_max_spd = max(speeds_map.values())
            if frame_max_spd > self._max_speed:
                self._max_speed = frame_max_spd
        mode = "TRACKING" if current_tracks else "SEARCHING"

        # 7. Render overlays — use live show_fps flag from RuntimeConfig
        annotated = self._visualizer.render(
            frame=frame,
            tracks=current_tracks,
            speeds=speeds_map,
            trajectories=traj_map,
            fps=current_fps if self._cfg.show_fps else None,
            mode=mode,
        )

        # 8. Convert BGR ndarray -> QPixmap, cache it, and emit
        pixmap = self._bgr_to_pixmap(annotated)
        self._last_pixmap = pixmap
        self.frame_ready.emit(pixmap)

        # 8b. Write to video recorder if active
        if self._recorder.is_recording:
            self._recorder.write(annotated)

        # 9. Emit per-frame stats — read already-computed values, no duplication.
        #    MetricsManager.get_metrics() was called above (stored in `m`).
        #    SpeedEstimator and BallTracker values are already in speeds_map /
        #    current_tracks — we only pick the "top" track for the panel.

        # Use runtime from MetricsManager instead of recomputing elapsed time
        runtime_secs = int(m["runtime"])

        if current_tracks:
            # Show the fastest-moving ball in the stats panel
            top_track = max(current_tracks,
                            key=lambda t: speeds_map.get(t["id"], 0.0))
            top_id    = str(top_track["id"])
            top_speed = speeds_map.get(top_track["id"], 0.0)
            # Highest-confidence detection this frame
            top_conf  = max((d["confidence"] for d in detections), default=0.0)
        else:
            # Nothing detected — show neutral/zero values as specified
            top_id    = "—"
            top_speed = 0.0
            top_conf  = 0.0

        self.stats_updated.emit({
            # fps / runtime come straight from MetricsManager — no recalculation
            "fps":          f"{m['current_fps']:.1f}",
            "detections":   str(len(detections)),        # 0 when nothing found
            "track_id":     top_id,                      # — when nothing found
            "speed":        f"{top_speed:.1f} px/s",     # 0.0 px/s when idle
            "confidence":   f"{top_conf:.2f}",           # 0.00 when idle
            "session_time": (f"{runtime_secs // 60:02d}"
                             f":{runtime_secs % 60:02d}"),
        })

        self._prev_track_ids = current_ids

    # ── Conversion helper ─────────────────────────────────────────────────────

    @staticmethod
    def _bgr_to_pixmap(frame: np.ndarray) -> QPixmap:
        """
        Convert an OpenCV BGR ndarray to a QPixmap in memory.

        BGR -> RGB -> QImage (Format_RGB888) -> QPixmap.
        .copy() detaches from the NumPy buffer before it is recycled.
        """
        rgb            = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch       = rgb.shape
        bytes_per_line = ch * w
        qimg           = QImage(
            rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
        )
        return QPixmap.fromImage(qimg.copy())
