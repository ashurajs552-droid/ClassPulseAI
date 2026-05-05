"""
ClassPulse AI — Emotion Detection Service

EfficientNetB3-based CNN for classroom emotion classification.
Classes: attentive, distracted, sleepy, confused, engaged.
Uses batch inference and rolling-average smoothing per student.
Target accuracy: 90%+ on FER2013+AffectNet combined.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Optional

import cv2
import numpy as np

from config import settings
from models.schemas import EmotionLabel, EmotionResult

logger = logging.getLogger(__name__)


class EmotionDetectionService:
    """CNN-based emotion classifier with batch inference and temporal smoothing."""

    EMOTION_CLASSES: list[str] = [
        "attentive", "distracted", "sleepy", "confused", "engaged",
    ]
    INPUT_SIZE: int = 48

    def __init__(self) -> None:
        self._confidence_threshold: float = settings.emotion_confidence_threshold
        self._smoothing_window: int = settings.emotion_smoothing_window
        self._model = None
        self._loaded = False

        # Rolling history per track_id → deque of softmax vectors
        self._history: dict[int, deque[np.ndarray]] = defaultdict(
            lambda: deque(maxlen=self._smoothing_window)
        )

    # ── Lifecycle ────────────────────────────────────────────

    def load(self, model_path: Optional[str] = None) -> None:
        """
        Load the emotion classification model.
        If no fine-tuned weights exist, builds an EfficientNetB3 architecture
        that can be trained separately.
        """
        if self._loaded:
            return

        try:
            import tensorflow as tf

            if model_path:
                self._model = tf.keras.models.load_model(model_path, compile=False)
                logger.info("Loaded emotion model from %s", model_path)
            else:
                # Build EfficientNetB3 architecture (pre-trained ImageNet backbone)
                base = tf.keras.applications.EfficientNetB3(
                    include_top=False,
                    weights="imagenet",
                    input_shape=(self.INPUT_SIZE, self.INPUT_SIZE, 3),
                    pooling="avg",
                )
                base.trainable = False  # freeze backbone for inference

                model = tf.keras.Sequential([
                    tf.keras.layers.InputLayer(input_shape=(self.INPUT_SIZE, self.INPUT_SIZE, 3)),
                    base,
                    tf.keras.layers.Dropout(0.3),
                    tf.keras.layers.Dense(256, activation="relu"),
                    tf.keras.layers.Dropout(0.2),
                    tf.keras.layers.Dense(len(self.EMOTION_CLASSES), activation="softmax"),
                ])
                self._model = model
                logger.info(
                    "Built EfficientNetB3 emotion model (ImageNet backbone, %d classes).",
                    len(self.EMOTION_CLASSES),
                )

            self._loaded = True
        except Exception as exc:
            logger.exception("Failed to load emotion model: %s", exc)

    def unload(self) -> None:
        """Release model and clear history."""
        self._model = None
        self._history.clear()
        self._loaded = False
        logger.info("Emotion detection unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Preprocessing ────────────────────────────────────────

    def _preprocess(self, face_crop: np.ndarray) -> np.ndarray:
        """
        Prepare a single face crop for the CNN.
        - Resize to 48×48
        - Convert to RGB if needed
        - Normalise pixel values [0, 1]
        """
        if face_crop.size == 0:
            return np.zeros((self.INPUT_SIZE, self.INPUT_SIZE, 3), dtype=np.float32)

        img = cv2.resize(face_crop, (self.INPUT_SIZE, self.INPUT_SIZE))

        # Ensure 3-channel
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        return img.astype(np.float32) / 255.0

    # ── Batch Inference ──────────────────────────────────────

    def detect_batch(
        self,
        face_crops: list[np.ndarray],
        track_ids: list[int],
        student_ids: list[Optional[str]] | None = None,
    ) -> list[EmotionResult]:
        """
        Classify emotions for a batch of face crops simultaneously.

        Args:
            face_crops: list of BGR face images (any size)
            track_ids: corresponding persistent tracker IDs
            student_ids: optional known student IDs

        Returns:
            list of EmotionResult (one per input face)
        """
        if not self._loaded or self._model is None:
            return self._fallback_results(track_ids, student_ids)

        if not face_crops:
            return []

        sids = student_ids or [None] * len(face_crops)

        # Preprocess all faces into a batch tensor
        batch = np.stack([self._preprocess(crop) for crop in face_crops])

        try:
            predictions = self._model.predict(batch, verbose=0)  # (N, 5)
        except Exception as exc:
            logger.error("Emotion batch inference failed: %s", exc)
            return self._fallback_results(track_ids, sids)

        results: list[EmotionResult] = []
        for i, (probs, tid) in enumerate(zip(predictions, track_ids)):
            # Add to rolling history
            self._history[tid].append(probs)

            # Compute smoothed probabilities
            smoothed = np.mean(list(self._history[tid]), axis=0)
            top_idx = int(np.argmax(smoothed))
            confidence = float(smoothed[top_idx])
            emotion = self.EMOTION_CLASSES[top_idx]

            raw_scores = {
                cls: round(float(smoothed[j]), 4)
                for j, cls in enumerate(self.EMOTION_CLASSES)
            }

            results.append(EmotionResult(
                student_id=sids[i] if i < len(sids) else None,
                track_id=tid,
                emotion=EmotionLabel(emotion),
                confidence=round(confidence, 4),
                raw_scores=raw_scores,
            ))

        return results

    def detect_single(
        self,
        face_crop: np.ndarray,
        track_id: int,
        student_id: Optional[str] = None,
    ) -> EmotionResult:
        """Classify emotion for a single face crop."""
        results = self.detect_batch([face_crop], [track_id], [student_id])
        if results:
            return results[0]
        return EmotionResult(
            student_id=student_id,
            track_id=track_id,
            emotion=EmotionLabel.distracted,
            confidence=0.0,
        )

    # ── Fallback ─────────────────────────────────────────────

    @staticmethod
    def _fallback_results(
        track_ids: list[int],
        student_ids: list[Optional[str]] | None,
    ) -> list[EmotionResult]:
        """Return neutral fallback results when the model isn't available."""
        sids = student_ids or [None] * len(track_ids)
        return [
            EmotionResult(
                student_id=sids[i] if i < len(sids) else None,
                track_id=tid,
                emotion=EmotionLabel.attentive,
                confidence=0.0,
                raw_scores={cls: 0.2 for cls in EmotionDetectionService.EMOTION_CLASSES},
            )
            for i, tid in enumerate(track_ids)
        ]

    # ── Utility ──────────────────────────────────────────────

    def clear_history(self, track_id: Optional[int] = None) -> None:
        """Clear smoothing history for one or all tracks."""
        if track_id is not None:
            self._history.pop(track_id, None)
        else:
            self._history.clear()

    def get_class_distribution(self) -> dict[str, int]:
        """
        Aggregate the most-recent prediction per tracked person
        into a class distribution dict.
        """
        dist: dict[str, int] = {cls: 0 for cls in self.EMOTION_CLASSES}
        for tid, history in self._history.items():
            if history:
                smoothed = np.mean(list(history), axis=0)
                top_cls = self.EMOTION_CLASSES[int(np.argmax(smoothed))]
                dist[top_cls] += 1
        return dist
