"""
ClassPulse AI — Face Recognition Service

Uses DeepFace with FaceNet512 for face verification.
Pre-caches all enrolled student embeddings on startup and matches
incoming face crops via cosine similarity (threshold 0.68).
Re-recognition happens every 30 frames per track (not every frame).
Includes anti-spoofing layer.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

import cv2
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from config import settings

logger = logging.getLogger(__name__)


class FaceRecognitionService:
    """DeepFace + FaceNet512 face recognition with caching."""

    def __init__(self) -> None:
        self._model_name: str = settings.recognition_model
        self._threshold: float = settings.recognition_threshold
        self._rerecognize_interval: int = settings.recognition_interval

        # Cache: student_id → numpy embedding (512-d)
        self._embeddings: dict[str, np.ndarray] = {}
        self._student_names: dict[str, str] = {}

        # Track recognition cache: track_id → (student_id, frames_since)
        self._track_cache: dict[int, tuple[Optional[str], int]] = {}

        # Anti-spoof model placeholder
        self._deepface_model = None
        self._loaded = False

    # ── Lifecycle ────────────────────────────────────────────

    def load(self, supabase_client=None) -> None:
        """
        Load the FaceNet512 model and pre-cache enrolled student embeddings
        from Supabase.
        """
        if self._loaded:
            return

        try:
            from deepface import DeepFace

            # Force-load the model by running a dummy representation
            dummy = np.zeros((48, 48, 3), dtype=np.uint8)
            try:
                DeepFace.represent(
                    img_path=dummy,
                    model_name=self._model_name,
                    enforce_detection=False,
                    detector_backend="skip",
                )
            except Exception:
                pass  # Model is now cached by DeepFace

            self._deepface_model = DeepFace
            logger.info("FaceNet512 model loaded via DeepFace.")
        except Exception as exc:
            logger.exception("Failed to load DeepFace model: %s", exc)
            return

        # Load enrolled embeddings from Supabase
        if supabase_client:
            self._load_embeddings_from_db(supabase_client)

        self._loaded = True
        logger.info(
            "Face recognition ready — %d enrolled students, threshold=%.2f",
            len(self._embeddings), self._threshold,
        )

    def _load_embeddings_from_db(self, client) -> None:
        """
        Fetch all active students with face_encoding from Supabase
        and cache as numpy arrays.
        """
        try:
            response = (
                client.table("students")
                .select("id, student_code, full_name, face_encoding")
                .eq("is_active", True)
                .not_.is_("face_encoding", "null")
                .execute()
            )
            for row in response.data or []:
                sid = row["id"]
                encoding = row.get("face_encoding")
                if encoding:
                    if isinstance(encoding, list):
                        vec = np.array(encoding, dtype=np.float32)
                    elif isinstance(encoding, str):
                        vec = np.fromstring(
                            encoding.strip("[]"), sep=",", dtype=np.float32
                        )
                    else:
                        continue
                    if vec.shape == (512,):
                        self._embeddings[sid] = vec
                        self._student_names[sid] = row.get("full_name", "Unknown")
            logger.info("Loaded %d face embeddings from Supabase.", len(self._embeddings))
        except Exception as exc:
            logger.exception("Error loading embeddings from Supabase: %s", exc)

    def unload(self) -> None:
        """Release model resources."""
        self._embeddings.clear()
        self._student_names.clear()
        self._track_cache.clear()
        self._deepface_model = None
        self._loaded = False
        logger.info("Face recognition unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def enrolled_count(self) -> int:
        return len(self._embeddings)

    # ── Recognition ──────────────────────────────────────────

    def recognize(
        self,
        face_crop: np.ndarray,
        track_id: int,
    ) -> tuple[Optional[str], Optional[str], float]:
        """
        Recognise a face crop.

        Uses the track cache to skip recognition if the same track was
        identified within the last ``recognition_interval`` frames.

        Returns:
            (student_id, student_name, confidence) or (None, None, 0.0)
        """
        if not self._loaded or self._deepface_model is None:
            return None, None, 0.0

        # Check cache — skip if recently recognised
        if track_id in self._track_cache:
            cached_id, frames = self._track_cache[track_id]
            if frames < self._rerecognize_interval and cached_id is not None:
                self._track_cache[track_id] = (cached_id, frames + 1)
                name = self._student_names.get(cached_id, "Unknown")
                return cached_id, name, 1.0  # cached match

        # No enrolled students → nothing to match against
        if not self._embeddings:
            self._track_cache[track_id] = (None, 0)
            return None, None, 0.0

        # Get embedding for the incoming face
        embedding = self._get_embedding(face_crop)
        if embedding is None:
            self._track_cache[track_id] = (None, 0)
            return None, None, 0.0

        # Anti-spoofing check
        if not self._anti_spoof_check(face_crop):
            logger.warning("Anti-spoof check failed for track %d", track_id)
            self._track_cache[track_id] = (None, 0)
            return None, None, 0.0

        # Cosine similarity against all enrolled embeddings
        best_id, best_name, best_score = self._match_embedding(embedding)

        if best_score >= self._threshold:
            self._track_cache[track_id] = (best_id, 0)
            return best_id, best_name, float(best_score)

        self._track_cache[track_id] = (None, 0)
        return None, None, float(best_score)

    def _get_embedding(self, face_crop: np.ndarray) -> Optional[np.ndarray]:
        """Extract a 512-d embedding from a face crop via DeepFace."""
        try:
            if face_crop.size == 0 or face_crop.shape[0] < 10 or face_crop.shape[1] < 10:
                return None

            result = self._deepface_model.represent(
                img_path=face_crop,
                model_name=self._model_name,
                enforce_detection=False,
                detector_backend="skip",
            )
            if result and isinstance(result, list) and len(result) > 0:
                vec = np.array(result[0]["embedding"], dtype=np.float32)
                if vec.shape == (512,):
                    return vec
            return None
        except Exception as exc:
            logger.debug("Embedding extraction failed: %s", exc)
            return None

    def _match_embedding(
        self, query: np.ndarray
    ) -> tuple[Optional[str], Optional[str], float]:
        """Find the best matching enrolled student via cosine similarity."""
        if not self._embeddings:
            return None, None, 0.0

        ids = list(self._embeddings.keys())
        db_matrix = np.stack([self._embeddings[sid] for sid in ids])  # (N, 512)
        query_2d = query.reshape(1, -1)  # (1, 512)

        similarities = cosine_similarity(query_2d, db_matrix)[0]  # (N,)
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])
        best_id = ids[best_idx]
        best_name = self._student_names.get(best_id, "Unknown")

        return best_id, best_name, best_score

    # ── Anti-spoofing ────────────────────────────────────────

    def _anti_spoof_check(self, face_crop: np.ndarray) -> bool:
        """
        Basic anti-spoofing heuristic based on Laplacian variance (blur detection)
        and colour histogram analysis.

        A flat/printed photo tends to have lower texture variance
        and unusual colour distribution.
        """
        try:
            if face_crop.size == 0:
                return False

            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

            # Laplacian variance — screens/prints are often blurrier
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            if laplacian_var < 15.0:
                logger.debug("Anti-spoof: low texture variance (%.1f)", laplacian_var)
                return False

            # Colour range check — printed faces have a narrower range
            hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
            sat_std = float(np.std(hsv[:, :, 1]))
            if sat_std < 5.0:
                logger.debug("Anti-spoof: low saturation std (%.1f)", sat_std)
                return False

            return True
        except Exception:
            return True  # fail open

    # ── Enrollment ───────────────────────────────────────────

    def enroll(
        self,
        student_id: str,
        student_name: str,
        face_image: np.ndarray,
    ) -> Optional[list[float]]:
        """
        Generate an embedding for a new student and add to the in-memory cache.
        Returns the embedding as a list for storage in Supabase.
        """
        embedding = self._get_embedding(face_image)
        if embedding is None:
            logger.error("Could not extract embedding for student %s", student_id)
            return None
        self._embeddings[student_id] = embedding
        self._student_names[student_id] = student_name
        logger.info("Enrolled student %s (%s)", student_id, student_name)
        return embedding.tolist()

    def remove(self, student_id: str) -> None:
        """Remove a student from the in-memory cache."""
        self._embeddings.pop(student_id, None)
        self._student_names.pop(student_id, None)

    def clear_track_cache(self) -> None:
        """Reset the per-track recognition cache (e.g. on new session)."""
        self._track_cache.clear()
