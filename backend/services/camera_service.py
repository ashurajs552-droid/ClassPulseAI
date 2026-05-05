"""
ClassPulse AI — Camera Service

Manages 4K video capture via OpenCV in a dedicated thread.
Frames are placed into a bounded queue for the processing pipeline.
Supports graceful shutdown and automatic reconnection.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from queue import Full, Queue
from typing import Optional

import cv2
import numpy as np

from config import settings

logger = logging.getLogger(__name__)


class CameraService:
    """Threaded 4K camera capture with frame buffering."""

    def __init__(
        self,
        source: int | str | None = None,
        capture_width: int | None = None,
        capture_height: int | None = None,
        process_width: int | None = None,
        process_height: int | None = None,
        fps: int | None = None,
        buffer_size: int | None = None,
    ) -> None:
        self._source = source if source is not None else settings.camera_source
        self._cap_w = capture_width or settings.capture_width
        self._cap_h = capture_height or settings.capture_height
        self._proc_w = process_width or settings.process_width
        self._proc_h = process_height or settings.process_height
        self._target_fps = fps or settings.capture_fps
        self._buffer_size = buffer_size or settings.frame_buffer_size

        self._capture: Optional[cv2.VideoCapture] = None
        self._frame_queue: Queue[np.ndarray] = Queue(maxsize=self._buffer_size)
        self._raw_frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()

        self._running = False
        self._capture_thread: Optional[threading.Thread] = None

        # FPS measurement
        self._fps_timestamps: deque[float] = deque(maxlen=30)
        self._current_fps: float = 0.0
        self._frame_count: int = 0

    # ── Public API ───────────────────────────────────────────

    def start(self) -> bool:
        """Open the camera and start the capture thread."""
        if self._running:
            logger.warning("Camera is already running.")
            return True

        success = self._open_capture()
        if not success:
            logger.error("Failed to open camera source: %s", self._source)
            return False

        self._running = True
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="camera-capture"
        )
        self._capture_thread.start()
        logger.info(
            "Camera started — source=%s  capture=%dx%d  process=%dx%d  fps=%d",
            self._source, self._cap_w, self._cap_h,
            self._proc_w, self._proc_h, self._target_fps,
        )
        return True

    def stop(self) -> None:
        """Gracefully stop capture and release the camera."""
        self._running = False
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=3.0)
        if self._capture and self._capture.isOpened():
            self._capture.release()
            self._capture = None
        # Drain the queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except Exception:
                break
        logger.info("Camera stopped.")

    def get_frame(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """
        Get the next processed (downscaled) frame from the buffer.
        Returns None if no frame is available within *timeout* seconds.
        """
        try:
            return self._frame_queue.get(timeout=timeout)
        except Exception:
            return None

    def get_raw_frame(self) -> Optional[np.ndarray]:
        """Get the most recent full-resolution frame (non-blocking)."""
        with self._lock:
            return self._raw_frame.copy() if self._raw_frame is not None else None

    @property
    def fps(self) -> float:
        """Current measured FPS."""
        return self._current_fps

    @property
    def frame_count(self) -> int:
        """Total frames captured since start."""
        return self._frame_count

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def resolution(self) -> tuple[int, int]:
        """Processing resolution (width, height)."""
        return (self._proc_w, self._proc_h)

    # ── Internals ────────────────────────────────────────────

    def _open_capture(self) -> bool:
        """Open the OpenCV VideoCapture with the desired resolution."""
        try:
            self._capture = cv2.VideoCapture(self._source)
            if not self._capture.isOpened():
                return False

            # Set capture resolution
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._cap_w)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._cap_h)
            self._capture.set(cv2.CAP_PROP_FPS, self._target_fps)

            # Reduce internal buffering
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 2)

            actual_w = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info("Capture opened — actual resolution: %dx%d", actual_w, actual_h)
            return True
        except Exception as exc:
            logger.exception("Error opening camera: %s", exc)
            return False

    def _capture_loop(self) -> None:
        """Continuously read frames and push downscaled copies to the queue."""
        frame_interval = 1.0 / self._target_fps

        while self._running:
            loop_start = time.perf_counter()

            if self._capture is None or not self._capture.isOpened():
                logger.warning("Camera disconnected — attempting reconnect…")
                time.sleep(2.0)
                if not self._open_capture():
                    continue

            ret, frame = self._capture.read()
            if not ret or frame is None:
                logger.warning("Failed to read frame — retrying…")
                time.sleep(0.05)
                continue

            # Store raw frame
            with self._lock:
                self._raw_frame = frame

            # Downscale for processing pipeline
            processed = cv2.resize(
                frame, (self._proc_w, self._proc_h), interpolation=cv2.INTER_LINEAR
            )

            # Push to queue (drop oldest if full)
            try:
                self._frame_queue.put_nowait(processed)
            except Full:
                try:
                    self._frame_queue.get_nowait()  # drop oldest
                except Exception:
                    pass
                try:
                    self._frame_queue.put_nowait(processed)
                except Exception:
                    pass

            # FPS tracking
            self._frame_count += 1
            now = time.perf_counter()
            self._fps_timestamps.append(now)
            if len(self._fps_timestamps) >= 2:
                elapsed = self._fps_timestamps[-1] - self._fps_timestamps[0]
                if elapsed > 0:
                    self._current_fps = (len(self._fps_timestamps) - 1) / elapsed

            # Throttle to target FPS
            elapsed = time.perf_counter() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("Capture loop exited.")

    # ── Demo / fallback ──────────────────────────────────────

    def generate_demo_frame(self) -> np.ndarray:
        """
        Generate a synthetic frame for demo / testing when no camera is available.
        Returns a 1920×1080 frame with a grid pattern and timestamp overlay.
        """
        frame = np.zeros((self._proc_h, self._proc_w, 3), dtype=np.uint8)
        frame[:] = (15, 15, 20)

        # Grid
        for x in range(0, self._proc_w, 80):
            cv2.line(frame, (x, 0), (x, self._proc_h), (30, 30, 40), 1)
        for y in range(0, self._proc_h, 80):
            cv2.line(frame, (0, y), (self._proc_w, y), (30, 30, 40), 1)

        # Timestamp
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            frame, f"ClassPulse AI — DEMO  {ts}",
            (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 240), 2,
        )

        # Simulated face rectangles
        import random
        for i in range(8):
            x1 = random.randint(100, self._proc_w - 200)
            y1 = random.randint(100, self._proc_h - 200)
            w, h = random.randint(80, 140), random.randint(100, 160)
            color = random.choice([(16, 185, 129), (245, 158, 11), (244, 63, 94)])
            cv2.rectangle(frame, (x1, y1), (x1 + w, y1 + h), color, 2)
            cv2.putText(
                frame, f"Student {i+1}",
                (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1,
            )

        return frame
