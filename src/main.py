"""
main.py - Entry point for the real-time ball detection and tracking system.

Pipeline per frame:
    camera -> detector -> tracker -> trajectory/speed -> metrics -> visualizer
"""

import sys
import time
from typing import Dict, List

import cv2

from camera import CameraManager
from config import MAX_TRAJECTORY_LENGTH, SHOW_FPS
from detector import BallDetector
from metrics import MetricsManager
from report import ReportGenerator
from speed import SpeedEstimator
from tracker import BallTracker
from trajectory import TrajectoryManager
from visualization import Visualizer

_WINDOW_NAME = "Ball Tracker  |  press Q to quit"


def _collect_speeds(
    tracks: List[Dict],
    speed_estimator: SpeedEstimator,
) -> Dict[int, float]:
    """Return a {track_id: speed} snapshot for the current active tracks."""
    return {t["id"]: speed_estimator.get_speed(t["id"]) for t in tracks}


def _avg_speed(speed_estimator: SpeedEstimator, track_ids: List[int]) -> float:
    """Compute mean speed across all active track IDs; returns 0.0 if none."""
    if not track_ids:
        return 0.0
    speeds = [speed_estimator.get_speed(tid) for tid in track_ids]
    return sum(speeds) / len(speeds)


def run() -> None:
    """
    Main loop: initialise all managers, process frames, and exit cleanly.

    Exits when the user presses 'q', or if the camera fails to open.
    On exit, releases the camera and saves session reports.
    """
    # ------------------------------------------------------------------ init
    camera      = CameraManager()
    detector    = BallDetector()
    tracker     = BallTracker()
    trajectories = TrajectoryManager(max_length=MAX_TRAJECTORY_LENGTH)
    speed_est   = SpeedEstimator()
    visualizer  = Visualizer()
    metrics     = MetricsManager()
    reporter    = ReportGenerator()

    # Session-level accumulators for the final report
    max_fps: float = 0.0
    tracks_created: int = 0
    prev_track_ids: set = set()

    # ----------------------------------------------------------------- camera
    if not camera.start():
        print("[ERROR] Could not open camera. Check CAMERA_INDEX in config.py.")
        sys.exit(1)

    cv2.namedWindow(_WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    print("[INFO] Starting — press Q to quit.")

    try:
        while True:
            frame_ts = time.time()
            success, frame = camera.read()

            if not success or frame is None:
                print("[WARNING] Failed to read frame — skipping.")
                continue

            # -------------------------------------------------------- detect
            detections = detector.detect(frame)

            # -------------------------------------------------------- track
            prev_ids_snapshot = {t["id"] for t in tracker.get_tracks()}
            tracker.update(detections)
            current_tracks = tracker.get_tracks()
            current_ids = {t["id"] for t in current_tracks}

            # Count newly spawned tracks
            new_ids = current_ids - prev_ids_snapshot
            tracks_created += len(new_ids)

            # Count tracks that disappeared this frame
            lost_count = len(prev_ids_snapshot - current_ids)

            # --------------------------------- trajectory + speed per track
            for track in current_tracks:
                tid = track["id"]
                center = track["center"]
                trajectories.update(tid, center)
                speed_est.update(tid, center, frame_ts)

            # Clean up state for tracks that were just lost
            for lost_id in (prev_ids_snapshot - current_ids):
                trajectories.clear(lost_id)
                speed_est.clear(lost_id)

            # ------------------------------------------------------- metrics
            metrics.update(
                detections=len(detections),
                lost_tracks=lost_count,
                timestamp=frame_ts,
            )
            m = metrics.get_metrics()
            current_fps: float = m["current_fps"]
            if current_fps > max_fps:
                max_fps = current_fps

            # --------------------------------------------- build traj dict
            traj_map = {
                t["id"]: trajectories.get_trajectory(t["id"])
                for t in current_tracks
                if trajectories.get_trajectory(t["id"]) is not None
            }
            speeds_map = _collect_speeds(current_tracks, speed_est)

            # -------------------------------------------------- visualize
            frame = visualizer.render(
                frame=frame,
                tracks=current_tracks,
                speeds=speeds_map,
                trajectories=traj_map,
                fps=current_fps if SHOW_FPS else None,
                mode="TRACKING" if current_tracks else "SEARCHING",
            )

            cv2.imshow(_WINDOW_NAME, frame)

            # ---------------------------------------------------- quit key
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("[INFO] Quit requested.")
                break

            prev_track_ids = current_ids

    except KeyboardInterrupt:
        print("[INFO] Interrupted by user.")

    finally:
        # ---------------------------------------------- cleanup + reports
        camera.release()
        cv2.destroyAllWindows()

        final_metrics = metrics.get_metrics()
        avg_spd = _avg_speed(speed_est, list(prev_track_ids))

        reporter.generate(
            metrics=final_metrics,
            max_fps=max_fps,
            avg_ball_speed=avg_spd,
            tracks_created=tracks_created,
        )
        json_path = reporter.save_json()
        txt_path  = reporter.save_text()
        print(f"[INFO] Reports saved:\n  {json_path}\n  {txt_path}")


if __name__ == "__main__":
    run()
