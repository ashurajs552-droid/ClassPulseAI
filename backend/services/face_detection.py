"""
ClassPulse AI — Face Detection Service

Uses MediaPipe BlazeFace (model_selection=1 for long-range) or OpenCV Haar cascades
to detect all faces in a frame. Handles multi-person classroom scale and returns
bounding boxes, landmarks, and confidence scores.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import cv2
import numpy as np

from config import settings
from models.schemas import BoundingBox, FaceDetection, FaceLandmarks

logger = logging.getLogger(__name__)


class FaceDetectionService:
    """MediaPipe & OpenCV face detector optimised for classroom scale."""

    def __init__(
        self,
        model_selection: int | None = None,
        min_confidence: float | None = None,
    ) -> None:
        self._model_selection = (
            model_selection if model_selection is not None
            else getattr(settings, "face_detection_model", 1)
        )
        self._min_confidence = min_confidence or getattr(settings, "face_detection_confidence", 0.6)
        self._detector = None
        self._haar_cascade = None
        self._loaded = False

    # ── Lifecycle ────────────────────────────────────────────

    def load(self) -> None:
        """Initialise the face detector (MediaPipe or OpenCV Haar fallback)."""
        if self._loaded:
            return

        # 1. Try MediaPipe BlazeFace
        try:
            import mediapipe as mp
            self._detector = mp.solutions.face_detection.FaceDetection(
                model_selection=self._model_selection,
                min_detection_confidence=self._min_confidence,
            )
            self._loaded = True
            logger.info("MediaPipe face detection loaded — model=%d", self._model_selection)
            return
        except Exception as mp_err:
            logger.warning("MediaPipe not available, falling back to OpenCV Haar: %s", mp_err)

        # 2. Fallback to OpenCV Haar Cascade
        try:
            cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            if os.path.exists(cascade_path):
                self._haar_cascade = cv2.CascadeClassifier(cascade_path)
                self._loaded = True
                logger.info("OpenCV Haar cascade face detector loaded.")
        except Exception as haar_err:
            logger.error("Failed to load OpenCV Haar face cascade: %s", haar_err)

    def unload(self) -> None:
        """Release detector resources."""
        if self._detector:
            try:
                self._detector.close()
            except Exception:
                pass
            self._detector = None
        self._haar_cascade = None
        self._loaded = False
        logger.info("Face detection unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Detection ────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> list[FaceDetection]:
        """
        Detect all faces in *frame* (BGR).
        """
        if not self._loaded:
            return []

        h, w = frame.shape[:2]

        # 1. Use MediaPipe if available
        if self._detector is not None:
            try:
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
                        x=max(0.0, float(bb.xmin)),
                        y=max(0.0, float(bb.ymin)),
                        w=min(1.0 - max(0.0, float(bb.xmin)), float(bb.width)),
                        h=min(1.0 - max(0.0, float(bb.ymin)), float(bb.height)),
                    )

                    kps = det.location_data.relative_keypoints
                    landmarks = FaceLandmarks(
                        right_eye=(float(kps[0].x), float(kps[0].y)) if len(kps) > 0 else (0, 0),
                        left_eye=(float(kps[1].x), float(kps[1].y)) if len(kps) > 1 else (0, 0),
                        nose_tip=(float(kps[2].x), float(kps[2].y)) if len(kps) > 2 else (0, 0),
                        mouth_center=(float(kps[3].x), float(kps[3].y)) if len(kps) > 3 else (0, 0),
                        right_ear=(float(kps[4].x), float(kps[4].y)) if len(kps) > 4 else (0, 0),
                        left_ear=(float(kps[5].x), float(kps[5].y)) if len(kps) > 5 else (0, 0),
                    )

                    faces.append(FaceDetection(
                        id=idx,
                        bbox=bbox,
                        landmarks=landmarks,
                        confidence=round(float(score), 4),
                    ))

                faces.sort(key=lambda f: f.confidence, reverse=True)
                return faces
            except Exception as e:
                logger.error("MediaPipe detection error: %s", e)

        # 2. Fallback to OpenCV Haar Cascade
        if self._haar_cascade is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
                rects = self._haar_cascade.detectMultiScale(
                    gray, scaleFactor=1.15, minNeighbors=4, minSize=(30, 30)
                )

                faces: list[FaceDetection] = []
                for idx, (rx, ry, rw, rh) in enumerate(rects):
                    bbox = BoundingBox(
                        x=max(0.0, float(rx / w)),
                        y=max(0.0, float(ry / h)),
                        w=min(1.0, float(rw / w)),
                        h=min(1.0, float(rh / h)),
                    )
                    landmarks = FaceLandmarks(
                        right_eye=(bbox.x + 0.3 * bbox.w, bbox.y + 0.35 * bbox.h),
                        left_eye=(bbox.x + 0.7 * bbox.w, bbox.y + 0.35 * bbox.h),
                        nose_tip=(bbox.x + 0.5 * bbox.w, bbox.y + 0.55 * bbox.h),
                        mouth_center=(bbox.x + 0.5 * bbox.w, bbox.y + 0.75 * bbox.h),
                        right_ear=(bbox.x + 0.1 * bbox.w, bbox.y + 0.45 * bbox.h),
                        left_ear=(bbox.x + 0.9 * bbox.w, bbox.y + 0.45 * bbox.h),
                    )
                    faces.append(FaceDetection(
                        id=idx,
                        bbox=bbox,
                        landmarks=landmarks,
                        confidence=0.92,
                    ))
                return faces
            except Exception as e:
                logger.error("OpenCV Haar detection error: %s", e)

        return []

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
