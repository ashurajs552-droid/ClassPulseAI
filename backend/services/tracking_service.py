"""
ClassPulse AI — Multi-Person Tracking Service

Uses DeepSORT to assign persistent IDs to each detected face across
frames.  Handles occlusion and re-entry with configurable max_age.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from config import settings
from models.schemas import BoundingBox, TrackInfo

logger = logging.getLogger(__name__)


class TrackingService:
    """DeepSORT-based multi-person tracker."""

    def __init__(self) -> None:
        self._max_age: int = settings.tracker_max_age
        self._n_init: int = settings.tracker_n_init
        self._tracker = None
        self._loaded = False

        # Mapping: track_id → student_id (enriched by face recognition)
        self._track_student_map: dict[int, str] = {}
        self._track_student_names: dict[int, str] = {}

    # ── Lifecycle ────────────────────────────────────────────

    def load(self) -> None:
        """Initialise the DeepSORT tracker."""
        if self._loaded:
            return

        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort

            self._tracker = DeepSort(
                max_age=self._max_age,
                n_init=self._n_init,
                max_cosine_distance=0.3,
                nn_budget=100,
                override_track_class=None,
                embedder="mobilenet",
                half=True,
                bgr=True,
                embedder_gpu=False,  # Use CPU; MPS not supported by DS
            )
            self._loaded = True
            logger.info(
                "DeepSORT tracker loaded — max_age=%d  n_init=%d",
                self._max_age, self._n_init,
            )
        except Exception as exc:
            logger.exception("Failed to load DeepSORT: %s", exc)

    def unload(self) -> None:
        """Release tracker resources."""
        self._tracker = None
        self._track_student_map.clear()
        self._track_student_names.clear()
        self._loaded = False
        logger.info("Tracking service unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Tracking ─────────────────────────────────────────────

    def update(
        self,
        frame: np.ndarray,
        bboxes: list[BoundingBox],
        confidences: list[float],
    ) -> list[TrackInfo]:
        """
        Update the tracker with new detections.

        Args:
            frame: current BGR frame
            bboxes: normalised bounding boxes from face detection
            confidences: corresponding confidence scores

        Returns:
            list of TrackInfo with persistent track IDs
        """
        if not self._loaded or self._tracker is None:
            # Fallback: assign sequential IDs without tracking
            return [
                TrackInfo(track_id=i, bbox=bb)
                for i, bb in enumerate(bboxes)
            ]

        h, w = frame.shape[:2]

        # Convert normalised bboxes to pixel [x1, y1, w, h] for DeepSORT
        raw_detections: list[tuple[list[float], float, str]] = []
        for bbox, conf in zip(bboxes, confidences):
            x1 = bbox.x * w
            y1 = bbox.y * h
            bw = bbox.w * w
            bh = bbox.h * h
            raw_detections.append(([x1, y1, bw, bh], conf, "face"))

        try:
            tracks = self._tracker.update_tracks(raw_detections, frame=frame)
        except Exception as exc:
            logger.error("DeepSORT update failed: %s", exc)
            return [
                TrackInfo(track_id=i, bbox=bb)
                for i, bb in enumerate(bboxes)
            ]

        results: list[TrackInfo] = []
        for track in tracks:
            if not track.is_confirmed():
                continue

            tid = track.track_id
            ltrb = track.to_ltrb()  # [left, top, right, bottom] in pixels
            bbox = BoundingBox(
                x=float(ltrb[0] / w),
                y=float(ltrb[1] / h),
                w=float((ltrb[2] - ltrb[0]) / w),
                h=float((ltrb[3] - ltrb[1]) / h),
            )

            results.append(TrackInfo(
                track_id=tid,
                bbox=bbox,
                student_id=self._track_student_map.get(tid),
                student_name=self._track_student_names.get(tid),
            ))

        return results

    # ── Student ↔ Track mapping ──────────────────────────────

    def set_student_for_track(
        self, track_id: int, student_id: str, student_name: str = ""
    ) -> None:
        """Associate a recognised student_id with a track_id."""
        self._track_student_map[track_id] = student_id
        self._track_student_names[track_id] = student_name

    def get_student_for_track(self, track_id: int) -> Optional[str]:
        """Get the student_id linked to a track, or None."""
        return self._track_student_map.get(track_id)

    def get_active_track_count(self) -> int:
        """Number of currently confirmed tracks."""
        if not self._loaded or self._tracker is None:
            return 0
        try:
            return sum(1 for t in self._tracker.tracker.tracks if t.is_confirmed())
        except Exception:
            return 0

    # ── Reset ────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all track state (e.g. on new session)."""
        self._track_student_map.clear()
        self._track_student_names.clear()
        if self._tracker:
            try:
                self._tracker.delete_all_tracks()
            except AttributeError:
                # Re-create tracker if delete not supported
                self.unload()
                self.load()
        logger.info("Tracker reset.")
