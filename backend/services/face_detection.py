"""
ClassPulse AI — Face Detection Service

Uses MediaPipe BlazeFace (model_selection=1 for long-range) to detect
all faces in a frame.  Handles 60+ simultaneous faces and returns
bounding boxes, landmarks, and confidence scores.
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

from config import settings
from models.schemas import BoundingBox, FaceDetection, FaceLandmarks

logger = logging.getLogger(__name__)


class FaceDetectionService:
    """MediaPipe-based face detector optimised for classroom scale."""

    def __init__(
        self,
        model_selection: int | None = None,
        min_confidence: float | None = None,
    ) -> None:
        self._model_selection = (
            model_selection if model_selection is not None
            else settings.face_detection_model
        )
        self._min_confidence = min_confidence or settings.face_detection_confidence
        self._detector: Optional[mp.solutions.face_detection.FaceDetection] = None
        self._mp_face = mp.solutions.face_detection
        self._mp_draw = mp.solutions.drawing_utils
        self._loaded = False

    # ── Lifecycle ────────────────────────────────────────────

    def load(self) -> None:
        """Initialise the MediaPipe face detector."""
        if self._loaded:
            return
        self._detector = self._mp_face.FaceDetection(
            model_selection=self._model_selection,
            min_detection_confidence=self._min_confidence,
        )
        self._loaded = True
        logger.info(
            "Face detection loaded — model=%d  confidence=%.2f",
            self._model_selection, self._min_confidence,
        )

    def unload(self) -> None:
        """Release MediaPipe resources."""
        if self._detector:
            self._detector.close()
            self._detector = None
        self._loaded = False
        logger.info("Face detection unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Detection ────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> list[FaceDetection]:
        """
        Detect all faces in *frame* (BGR).

        Returns a list of ``FaceDetection`` objects sorted by confidence
        (highest first).  Handles 60+ simultaneous detections.
        """
        if not self._loaded or self._detector is None:
            logger.error("Face detector not loaded — call load() first.")
            return []

        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False

        results = self._detector.process(rgb)

        if not results.detections:
            return []

        faces: list[FaceDetection] = []
        for idx, det in enumerate(results.detections):
            score = det.score[0] if det.score else 0.0
            if score < self._min_confidence:
                continue

            bb = det.location_data.relative_bounding_box
            bbox = BoundingBox(
                x=max(0.0, bb.xmin),
                y=max(0.0, bb.ymin),
                w=min(1.0 - max(0.0, bb.xmin), bb.width),
                h=min(1.0 - max(0.0, bb.ymin), bb.height),
            )

            # Extract key-point landmarks
            kps = det.location_data.relative_keypoints
            landmarks = FaceLandmarks(
                right_eye=(kps[0].x, kps[0].y) if len(kps) > 0 else (0, 0),
                left_eye=(kps[1].x, kps[1].y) if len(kps) > 1 else (0, 0),
                nose_tip=(kps[2].x, kps[2].y) if len(kps) > 2 else (0, 0),
                mouth_center=(kps[3].x, kps[3].y) if len(kps) > 3 else (0, 0),
                right_ear=(kps[4].x, kps[4].y) if len(kps) > 4 else (0, 0),
                left_ear=(kps[5].x, kps[5].y) if len(kps) > 5 else (0, 0),
            )

            faces.append(FaceDetection(
                id=idx,
                bbox=bbox,
                landmarks=landmarks,
                confidence=round(score, 4),
            ))

        faces.sort(key=lambda f: f.confidence, reverse=True)
        return faces

    # ── Cropping helper ──────────────────────────────────────

    @staticmethod
    def crop_face(
        frame: np.ndarray,
        bbox: BoundingBox,
        margin: float = 0.15,
    ) -> np.ndarray:
        """
        Crop a face region from *frame* using the normalised *bbox*
        with an optional margin expansion.
        """
        h, w, _ = frame.shape
        x1 = int(max(0, (bbox.x - margin * bbox.w) * w))
        y1 = int(max(0, (bbox.y - margin * bbox.h) * h))
        x2 = int(min(w, (bbox.x + bbox.w + margin * bbox.w) * w))
        y2 = int(min(h, (bbox.y + bbox.h + margin * bbox.h) * h))
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return np.zeros((48, 48, 3), dtype=np.uint8)
        return crop

    # ── Drawing helper ───────────────────────────────────────

    @staticmethod
    def draw_detections(
        frame: np.ndarray,
        faces: list[FaceDetection],
        color: tuple[int, int, int] = (99, 102, 241),
        thickness: int = 2,
        label_fn=None,
    ) -> np.ndarray:
        """
        Draw bounding boxes and optional labels on *frame* (mutates in-place).

        *label_fn*: callable(FaceDetection) → str  for custom labels.
        """
        h, w, _ = frame.shape
        for face in faces:
            x1 = int(face.bbox.x * w)
            y1 = int(face.bbox.y * h)
            x2 = int((face.bbox.x + face.bbox.w) * w)
            y2 = int((face.bbox.y + face.bbox.h) * h)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

            label = (
                label_fn(face)
                if label_fn
                else f"{face.confidence:.0%}"
            )

            (tw, th), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1,
            )
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(
                frame, label,
                (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            )

        return frame
