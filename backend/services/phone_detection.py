"""
ClassPulse AI — Phone Detection Service

Uses Ultralytics YOLOv8x to detect mobile phones in classroom frames.
Matches each phone detection to the nearest student bounding box and
triggers alerts.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from config import settings
from models.schemas import BoundingBox, PhoneDetection

logger = logging.getLogger(__name__)

# COCO class ID for "cell phone"
CELL_PHONE_CLASS_ID = 67


class PhoneDetectionService:
    """YOLOv8x-based mobile phone detector."""

    def __init__(self) -> None:
        self._model_path: str = settings.yolo_model_path
        self._confidence: float = settings.yolo_confidence
        self._nms: float = settings.yolo_nms_threshold
        self._model = None
        self._loaded = False

    # ── Lifecycle ────────────────────────────────────────────

    def load(self) -> None:
        """Load the YOLOv8x model."""
        if self._loaded:
            return

        try:
            from ultralytics import YOLO

            self._model = YOLO(self._model_path)

            # Attempt MPS acceleration on Apple Silicon
            try:
                import torch
                if torch.backends.mps.is_available():
                    self._model.to("mps")
                    logger.info("YOLOv8x loaded on MPS (Apple Silicon).")
                else:
                    logger.info("YOLOv8x loaded on CPU.")
            except Exception:
                logger.info("YOLOv8x loaded on CPU (MPS not available).")

            self._loaded = True
            logger.info(
                "Phone detection ready — model=%s  conf=%.2f  nms=%.2f",
                self._model_path, self._confidence, self._nms,
            )
        except Exception as exc:
            logger.exception("Failed to load YOLO model: %s", exc)

    def unload(self) -> None:
        """Release model resources."""
        self._model = None
        self._loaded = False
        logger.info("Phone detection unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Detection ────────────────────────────────────────────

    def detect(
        self,
        frame: np.ndarray,
        student_bboxes: list[tuple[Optional[str], BoundingBox]] | None = None,
    ) -> list[PhoneDetection]:
        """
        Detect mobile phones in *frame* (BGR).

        Args:
            frame: input image (BGR, any resolution)
            student_bboxes: optional list of (student_id, BoundingBox) to
                            associate phone detections with nearby students.

        Returns:
            list of PhoneDetection objects
        """
        if not self._loaded or self._model is None:
            return []

        h, w = frame.shape[:2]

        try:
            results = self._model.predict(
                source=frame,
                conf=self._confidence,
                iou=self._nms,
                classes=[CELL_PHONE_CLASS_ID],
                verbose=False,
                stream=False,
            )
        except Exception as exc:
            logger.error("YOLO inference failed: %s", exc)
            return []

        detections: list[PhoneDetection] = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                cls_id = int(box.cls[0]) if box.cls is not None else -1
                if cls_id != CELL_PHONE_CLASS_ID:
                    continue

                conf = float(box.conf[0]) if box.conf is not None else 0.0
                if conf < self._confidence:
                    continue

                # Convert xyxy to normalised xywh
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = xyxy
                bbox = BoundingBox(
                    x=float(x1 / w),
                    y=float(y1 / h),
                    w=float((x2 - x1) / w),
                    h=float((y2 - y1) / h),
                )

                # Find nearest student
                nearby_id, nearby_track = self._find_nearest_student(
                    bbox, student_bboxes
                )

                detections.append(PhoneDetection(
                    bbox=bbox,
                    confidence=round(conf, 4),
                    nearby_student_id=nearby_id,
                    nearby_track_id=nearby_track,
                ))

        if detections:
            logger.info("Detected %d phone(s) in frame.", len(detections))

        return detections

    # ── Proximity matching ───────────────────────────────────

    @staticmethod
    def _find_nearest_student(
        phone_bbox: BoundingBox,
        student_bboxes: list[tuple[Optional[str], BoundingBox]] | None,
    ) -> tuple[Optional[str], Optional[int]]:
        """
        Find the student bbox closest to the phone bbox (centre distance).
        Returns (student_id, None) — track_id enrichment happens upstream.
        """
        if not student_bboxes:
            return None, None

        phone_cx = phone_bbox.x + phone_bbox.w / 2
        phone_cy = phone_bbox.y + phone_bbox.h / 2

        best_dist = float("inf")
        best_id: Optional[str] = None

        for sid, sb in student_bboxes:
            scx = sb.x + sb.w / 2
            scy = sb.y + sb.h / 2
            dist = ((phone_cx - scx) ** 2 + (phone_cy - scy) ** 2) ** 0.5

            # Only consider students within reasonable proximity
            max_proximity = max(sb.w, sb.h) * 2.0
            if dist < best_dist and dist < max_proximity:
                best_dist = dist
                best_id = sid

        return best_id, None

    # ── Overlay drawing ──────────────────────────────────────

    @staticmethod
    def draw_detections(
        frame: np.ndarray,
        phones: list[PhoneDetection],
        color: tuple[int, int, int] = (0, 0, 255),
        thickness: int = 2,
    ) -> np.ndarray:
        """Draw phone bounding boxes on *frame* with a 📱 label."""
        import cv2

        h, w = frame.shape[:2]
        for phone in phones:
            x1 = int(phone.bbox.x * w)
            y1 = int(phone.bbox.y * h)
            x2 = int((phone.bbox.x + phone.bbox.w) * w)
            y2 = int((phone.bbox.y + phone.bbox.h) * h)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
            label = f"PHONE {phone.confidence:.0%}"
            cv2.putText(
                frame, label,
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
            )

        return frame
