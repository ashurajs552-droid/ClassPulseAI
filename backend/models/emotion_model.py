"""
ClassPulse AI — Emotion Detection Model (Inference)

Wraps the trained EfficientNetB3 for production inference.

Features:
  - Batch prediction on multiple face crops
  - Per-student temporal smoothing (exponential moving average)
  - Thread-safe model loaded once into memory
  - MPS / CUDA / CPU auto-selection
  - Returns class label + confidence + full probability distribution

Usage:
    from models.emotion_model import EmotionModel

    model = EmotionModel()
    model.load("./models/emotion_efficientnetb3_best.pth")

    results = model.predict(face_crops)
    # [{"emotion": "attentive", "confidence": 0.93, "probs": {...}}, ...]

    smoothed = model.predict_with_smoothing("stu001", crop)
    # {"emotion": "attentive", "confidence": 0.91, "probs": {...}}
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms

logger = logging.getLogger(__name__)

CLASSES = ["attentive", "confused", "distracted", "engaged", "sleepy"]
IMG_SIZE = 224


class EmotionModel:
    """
    EfficientNetB3-based emotion classifier.

    Loads once, stays in memory, supports batch inference.
    """

    def __init__(self) -> None:
        self._model: Optional[nn.Module] = None
        self._device: Optional[torch.device] = None
        self._transform: Optional[transforms.Compose] = None
        self._classes: list[str] = CLASSES
        self._is_loaded = False
        self._lock = threading.Lock()

        # Temporal smoothing buffers: student_id → EMA probability vector
        self._smooth_alpha = 0.4  # new observation weight
        self._smooth_buffers: dict[str, np.ndarray] = defaultdict(
            lambda: np.ones(len(CLASSES)) / len(CLASSES)
        )

    # ── Load / unload ────────────────────────────────────────

    def load(self, checkpoint_path: str = "./models/emotion_efficientnetb3_best.pth") -> None:
        """Load model weights from a training checkpoint."""
        if self._is_loaded:
            logger.info("Emotion model already loaded.")
            return

        if not os.path.exists(checkpoint_path):
            logger.error("Emotion checkpoint not found: %s", checkpoint_path)
            raise FileNotFoundError(checkpoint_path)

        # Device
        if torch.cuda.is_available():
            self._device = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self._device = torch.device("mps")
        else:
            self._device = torch.device("cpu")

        # Load checkpoint
        ckpt = torch.load(checkpoint_path, map_location=self._device, weights_only=False)
        config = ckpt.get("config", {})
        num_classes = config.get("num_classes", len(CLASSES))
        self._classes = ckpt.get("class_names", CLASSES)

        # Build model
        model = models.efficientnet_b3(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=0.4),
            nn.Linear(in_features, 512),
            nn.ReLU(inplace=True),
            nn.BatchNorm1d(512),
            nn.Dropout(p=0.2),
            nn.Linear(512, num_classes),
        )
        model.load_state_dict(ckpt["model_state_dict"])
        model = model.to(self._device)
        model.eval()

        self._model = model

        # Transform (val/inference — no augmentation)
        self._transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        self._is_loaded = True
        logger.info(
            "✓ Emotion model loaded on %s (classes: %s, epoch: %d, val_acc: %.2f%%)",
            self._device, self._classes, ckpt.get("epoch", 0), ckpt.get("val_acc", 0),
        )

    def unload(self) -> None:
        """Release model from memory."""
        self._model = None
        self._device = None
        self._is_loaded = False
        self._smooth_buffers.clear()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Emotion model unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def classes(self) -> list[str]:
        return list(self._classes)

    # ── Preprocessing ────────────────────────────────────────

    def _preprocess(self, face_crops: list[np.ndarray]) -> torch.Tensor:
        """
        Preprocess a list of face crops (BGR uint8, any size) into a batched tensor.

        Steps:
          1. Resize to 224×224
          2. BGR → RGB
          3. Apply normalization
          4. Stack into batch tensor
        """
        tensors: list[torch.Tensor] = []

        for crop in face_crops:
            # Ensure valid crop
            if crop is None or crop.size == 0:
                # Use a black image as placeholder
                crop = np.zeros((IMG_SIZE, IMG_SIZE, 3), dtype=np.uint8)

            # Resize
            if crop.shape[0] != IMG_SIZE or crop.shape[1] != IMG_SIZE:
                crop = cv2.resize(crop, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_LINEAR)

            # BGR → RGB
            if len(crop.shape) == 3 and crop.shape[2] == 3:
                crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            elif len(crop.shape) == 2:
                # Grayscale → RGB
                crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)

            tensors.append(self._transform(crop))

        return torch.stack(tensors)

    # ── Batch prediction ─────────────────────────────────────

    def predict(self, face_crops: list[np.ndarray]) -> list[dict]:
        """
        Batch predict emotions for a list of face crops.

        Args:
            face_crops: list of BGR uint8 numpy arrays (any size)

        Returns:
            list of dicts: [{"emotion": str, "confidence": float, "probs": {str: float}}]
        """
        if not self._is_loaded or not face_crops:
            return [{"emotion": "unknown", "confidence": 0.0, "probs": {}} for _ in face_crops]

        with self._lock:
            batch = self._preprocess(face_crops).to(self._device)

            with torch.no_grad():
                logits = self._model(batch)
                probs = torch.softmax(logits, dim=1).cpu().numpy()

        results: list[dict] = []
        for prob_vec in probs:
            top_idx = int(np.argmax(prob_vec))
            results.append({
                "emotion": self._classes[top_idx],
                "confidence": float(prob_vec[top_idx]),
                "probs": {cls: float(p) for cls, p in zip(self._classes, prob_vec)},
            })

        return results

    # ── Single prediction with temporal smoothing ────────────

    def predict_with_smoothing(
        self, student_id: str, face_crop: np.ndarray
    ) -> dict:
        """
        Predict with exponential moving average smoothing.

        Each student has a per-class probability buffer that is updated
        with each new observation. This reduces jitter in frame-by-frame
        classifications.

        Args:
            student_id: unique student identifier
            face_crop: BGR uint8 numpy array

        Returns:
            {"emotion": str, "confidence": float, "probs": {str: float}}
        """
        raw_results = self.predict([face_crop])
        if not raw_results:
            return {"emotion": "unknown", "confidence": 0.0, "probs": {}}

        raw = raw_results[0]
        raw_probs = np.array([raw["probs"].get(cls, 0.0) for cls in self._classes])

        # EMA update
        prev = self._smooth_buffers[student_id]
        smoothed = self._smooth_alpha * raw_probs + (1 - self._smooth_alpha) * prev
        self._smooth_buffers[student_id] = smoothed

        top_idx = int(np.argmax(smoothed))
        return {
            "emotion": self._classes[top_idx],
            "confidence": float(smoothed[top_idx]),
            "probs": {cls: float(p) for cls, p in zip(self._classes, smoothed)},
            "raw_emotion": raw["emotion"],
            "raw_confidence": raw["confidence"],
        }

    def reset_smoothing(self, student_id: Optional[str] = None) -> None:
        """Reset smoothing buffer(s)."""
        if student_id:
            self._smooth_buffers.pop(student_id, None)
        else:
            self._smooth_buffers.clear()

    # ── Convenience ──────────────────────────────────────────

    def predict_single(self, face_crop: np.ndarray) -> dict:
        """Predict emotion for a single face crop (no smoothing)."""
        results = self.predict([face_crop])
        return results[0] if results else {"emotion": "unknown", "confidence": 0.0, "probs": {}}

    def benchmark(self, num_faces: int = 60, warmup: int = 5, runs: int = 20) -> dict:
        """
        Benchmark batch inference latency.

        Returns:
            {"avg_ms": float, "per_face_ms": float, "p95_ms": float}
        """
        if not self._is_loaded:
            return {"error": "Model not loaded"}

        fake_crops = [
            np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
            for _ in range(num_faces)
        ]

        # Warmup
        for _ in range(warmup):
            self.predict(fake_crops)

        times: list[float] = []
        for _ in range(runs):
            t0 = time.time()
            self.predict(fake_crops)
            times.append((time.time() - t0) * 1000)

        return {
            "num_faces": num_faces,
            "avg_ms": float(np.mean(times)),
            "per_face_ms": float(np.mean(times) / num_faces),
            "p95_ms": float(np.percentile(times, 95)),
            "min_ms": float(np.min(times)),
            "device": str(self._device),
        }
