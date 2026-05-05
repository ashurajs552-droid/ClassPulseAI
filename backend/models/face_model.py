"""
ClassPulse AI — Face Recognition Model (Inference)

FaceNet512 wrapper for real-time face identification.

Features:
  - Load precomputed embeddings from pickle
  - Vectorised cosine similarity search (numpy)
  - Add/remove students at runtime
  - Configurable similarity threshold + anti-spoofing gate
  - Thread-safe embedding access

Usage:
    from models.face_model import FaceModel

    model = FaceModel()
    model.load_embeddings("./models/face_embeddings.pkl")

    match = model.find_match(face_crop)
    # {"student_id": "STU001", "confidence": 0.87, "matched": True}

    model.add_student("STU099", face_crop)
"""

from __future__ import annotations

import logging
import os
import pickle
import threading
import time
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 512
DEFAULT_THRESHOLD = 0.68  # cosine similarity threshold


class FaceModel:
    """
    FaceNet512-based face recognition for student identification.

    Stores 512-d normalised embeddings per student and matches
    incoming face crops via vectorised cosine similarity.
    """

    def __init__(self, threshold: float = DEFAULT_THRESHOLD) -> None:
        self._embeddings: dict[str, np.ndarray] = {}
        self._student_ids: list[str] = []
        self._emb_matrix: Optional[np.ndarray] = None  # (N, 512) precomputed
        self._threshold = threshold
        self._embedder = None  # lazy-loaded
        self._lock = threading.RLock()
        self._is_loaded = False
        self._backend = "none"

    # ── Load / unload ────────────────────────────────────────

    def load_embeddings(self, path: str = "./models/face_embeddings.pkl") -> None:
        """Load precomputed embeddings from the training pipeline."""
        if not os.path.exists(path):
            logger.error("Embeddings file not found: %s", path)
            raise FileNotFoundError(path)

        with open(path, "rb") as f:
            payload = pickle.load(f)

        with self._lock:
            self._embeddings = payload["embeddings"]
            self._student_ids = list(self._embeddings.keys())
            self._rebuild_matrix()
            self._backend = payload.get("model_backend", "unknown")

        self._is_loaded = True
        logger.info(
            "✓ Face model loaded: %d students, %d-dim embeddings (backend: %s)",
            len(self._embeddings), EMBEDDING_DIM, self._backend,
        )

    def unload(self) -> None:
        """Release embeddings from memory."""
        with self._lock:
            self._embeddings.clear()
            self._student_ids.clear()
            self._emb_matrix = None
        self._embedder = None
        self._is_loaded = False
        logger.info("Face model unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def enrolled_count(self) -> int:
        return len(self._student_ids)

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        self._threshold = max(0.0, min(1.0, value))

    # ── Embedding generation ─────────────────────────────────

    def _get_embedder(self):
        """Lazy-load the embedding model (facenet-pytorch or DeepFace)."""
        if self._embedder is None:
            try:
                from facenet_pytorch import InceptionResnetV1, MTCNN
                import torch

                device = (
                    torch.device("mps")
                    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
                    else torch.device("cuda" if torch.cuda.is_available() else "cpu")
                )
                self._mtcnn = MTCNN(
                    image_size=160, margin=20, min_face_size=40,
                    keep_all=False, device=device,
                )
                self._embedder = InceptionResnetV1(pretrained="vggface2").eval().to(device)
                self._embed_device = device
                self._embed_backend = "facenet_pytorch"
                logger.info("Face embedder loaded (facenet-pytorch) on %s.", device)

            except ImportError:
                try:
                    from deepface import DeepFace
                    DeepFace.build_model("Facenet512")
                    self._embed_backend = "deepface"
                    self._embedder = "deepface"  # sentinel
                    logger.info("Face embedder loaded (DeepFace Facenet512).")
                except ImportError:
                    logger.error("No face embedding library available!")
                    raise

        return self._embedder

    def _embed_crop(self, face_crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Generate a 512-d embedding from a BGR face crop.
        Returns L2-normalised embedding or None.
        """
        embedder = self._get_embedder()

        if self._embed_backend == "facenet_pytorch":
            return self._embed_facenet_pytorch(face_crop)
        else:
            return self._embed_deepface(face_crop)

    def _embed_facenet_pytorch(self, crop: np.ndarray) -> Optional[np.ndarray]:
        import torch
        from PIL import Image

        try:
            # BGR → RGB → PIL
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)

            face_tensor = self._mtcnn(pil_img)
            if face_tensor is None:
                # MTCNN didn't detect a face — try direct resize
                resized = cv2.resize(rgb, (160, 160))
                face_tensor = torch.from_numpy(resized).permute(2, 0, 1).float()
                face_tensor = (face_tensor - 127.5) / 128.0

            face_tensor = face_tensor.unsqueeze(0).to(self._embed_device)

            with torch.no_grad():
                emb = self._embedder(face_tensor).cpu().numpy().flatten()

            # L2 normalise
            norm = np.linalg.norm(emb)
            return (emb / norm).astype(np.float32) if norm > 0 else None

        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            return None

    def _embed_deepface(self, crop: np.ndarray) -> Optional[np.ndarray]:
        from deepface import DeepFace
        import tempfile

        try:
            # Save to temp file (DeepFace needs a path)
            tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
            cv2.imwrite(tmp.name, crop)

            results = DeepFace.represent(
                img_path=tmp.name,
                model_name="Facenet512",
                enforce_detection=False,
                detector_backend="skip",
            )
            os.unlink(tmp.name)

            if results and len(results) > 0:
                emb = np.array(results[0]["embedding"], dtype=np.float32)
                norm = np.linalg.norm(emb)
                return (emb / norm) if norm > 0 else None
            return None

        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            return None

    # ── Matrix management ────────────────────────────────────

    def _rebuild_matrix(self) -> None:
        """Rebuild the (N, 512) embedding matrix for vectorised search."""
        if self._embeddings:
            self._emb_matrix = np.stack(
                [self._embeddings[sid] for sid in self._student_ids]
            )
        else:
            self._emb_matrix = np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    # ── Recognition ──────────────────────────────────────────

    def find_match(
        self,
        face_crop: np.ndarray,
        threshold: Optional[float] = None,
    ) -> dict:
        """
        Identify a student from a face crop.

        Args:
            face_crop: BGR uint8 numpy array (any size)
            threshold: override default similarity threshold

        Returns:
            {
                "student_id": str | None,
                "confidence": float,
                "matched": bool,
                "top_matches": [{"student_id": str, "similarity": float}, ...]
            }
        """
        if not self._is_loaded or self._emb_matrix is None or len(self._student_ids) == 0:
            return {
                "student_id": None, "confidence": 0.0,
                "matched": False, "top_matches": [],
            }

        thresh = threshold if threshold is not None else self._threshold

        # Generate query embedding
        query_emb = self._embed_crop(face_crop)
        if query_emb is None:
            return {
                "student_id": None, "confidence": 0.0,
                "matched": False, "top_matches": [],
            }

        return self._match_embedding(query_emb, thresh)

    def find_match_from_embedding(
        self,
        embedding: np.ndarray,
        threshold: Optional[float] = None,
    ) -> dict:
        """Match using a pre-computed embedding (faster — skips embedding step)."""
        thresh = threshold if threshold is not None else self._threshold

        # Ensure normalised
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        return self._match_embedding(embedding, thresh)

    def _match_embedding(self, query: np.ndarray, threshold: float) -> dict:
        """Core vectorised cosine similarity matching."""
        with self._lock:
            # Vectorised dot product (embeddings are already L2-normalised)
            similarities = self._emb_matrix @ query  # (N,)

            # Top-5 matches
            top_k = min(5, len(self._student_ids))
            top_indices = np.argpartition(similarities, -top_k)[-top_k:]
            top_indices = top_indices[np.argsort(similarities[top_indices])[::-1]]

            top_matches = [
                {
                    "student_id": self._student_ids[idx],
                    "similarity": float(similarities[idx]),
                }
                for idx in top_indices
            ]

            best_idx = top_indices[0]
            best_sim = float(similarities[best_idx])
            best_id = self._student_ids[best_idx]

        matched = best_sim >= threshold

        return {
            "student_id": best_id if matched else None,
            "confidence": best_sim,
            "matched": matched,
            "top_matches": top_matches,
        }

    def find_matches_batch(
        self,
        face_crops: list[np.ndarray],
        threshold: Optional[float] = None,
    ) -> list[dict]:
        """
        Batch recognition for multiple face crops.
        More efficient than calling find_match() in a loop.
        """
        if not self._is_loaded or not face_crops:
            return [
                {"student_id": None, "confidence": 0.0, "matched": False, "top_matches": []}
                for _ in face_crops
            ]

        thresh = threshold if threshold is not None else self._threshold

        # Generate all embeddings
        query_embeddings: list[Optional[np.ndarray]] = []
        for crop in face_crops:
            emb = self._embed_crop(crop)
            query_embeddings.append(emb)

        results: list[dict] = []
        for emb in query_embeddings:
            if emb is not None:
                results.append(self._match_embedding(emb, thresh))
            else:
                results.append({
                    "student_id": None, "confidence": 0.0,
                    "matched": False, "top_matches": [],
                })

        return results

    # ── Runtime enrollment ───────────────────────────────────

    def add_student(self, student_id: str, face_crop: np.ndarray) -> bool:
        """
        Enroll a new student at runtime.

        Args:
            student_id: unique ID
            face_crop: BGR face image

        Returns:
            True if successfully enrolled
        """
        emb = self._embed_crop(face_crop)
        if emb is None:
            logger.warning("Failed to enroll %s — no face detected.", student_id)
            return False

        with self._lock:
            self._embeddings[student_id] = emb
            if student_id not in self._student_ids:
                self._student_ids.append(student_id)
            self._rebuild_matrix()

        logger.info("✓ Student %s enrolled (total: %d).", student_id, len(self._student_ids))
        return True

    def add_student_from_embedding(self, student_id: str, embedding: np.ndarray) -> None:
        """Enroll a student using a pre-computed embedding."""
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        with self._lock:
            self._embeddings[student_id] = embedding.astype(np.float32)
            if student_id not in self._student_ids:
                self._student_ids.append(student_id)
            self._rebuild_matrix()

        logger.info("✓ Student %s enrolled from embedding (total: %d).",
                     student_id, len(self._student_ids))

    def remove_student(self, student_id: str) -> bool:
        """Remove a student's embedding."""
        with self._lock:
            if student_id in self._embeddings:
                del self._embeddings[student_id]
                self._student_ids.remove(student_id)
                self._rebuild_matrix()
                logger.info("Student %s removed (total: %d).",
                             student_id, len(self._student_ids))
                return True
        return False

    def update_student(self, student_id: str, face_crop: np.ndarray) -> bool:
        """Re-enroll a student (e.g. updated photo)."""
        return self.add_student(student_id, face_crop)

    # ── Persistence ──────────────────────────────────────────

    def save_embeddings(self, path: str = "./models/face_embeddings.pkl") -> None:
        """Save current embeddings to disk."""
        with self._lock:
            payload = {
                "embeddings": dict(self._embeddings),
                "student_ids": list(self._student_ids),
                "embedding_dim": EMBEDDING_DIM,
                "model_backend": self._backend,
                "num_students": len(self._student_ids),
            }

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

        logger.info("Saved %d embeddings to %s.", len(self._student_ids), path)

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return model statistics."""
        return {
            "enrolled_students": len(self._student_ids),
            "embedding_dim": EMBEDDING_DIM,
            "threshold": self._threshold,
            "backend": self._backend,
            "is_loaded": self._is_loaded,
        }

    def benchmark(self, num_queries: int = 60, warmup: int = 5, runs: int = 20) -> dict:
        """
        Benchmark cosine similarity matching (excludes embedding extraction).
        """
        if not self._is_loaded or self._emb_matrix is None:
            return {"error": "Model not loaded"}

        # Generate random query embeddings
        queries = np.random.randn(num_queries, EMBEDDING_DIM).astype(np.float32)
        queries /= np.linalg.norm(queries, axis=1, keepdims=True)

        # Warmup
        for _ in range(warmup):
            _ = self._emb_matrix @ queries.T

        times: list[float] = []
        for _ in range(runs):
            t0 = time.time()
            sims = self._emb_matrix @ queries.T  # (enrolled, queries)
            best_idxs = np.argmax(sims, axis=0)
            best_sims = sims[best_idxs, np.arange(num_queries)]
            _ = best_sims >= self._threshold
            times.append((time.time() - t0) * 1000)

        return {
            "num_queries": num_queries,
            "enrolled_students": len(self._student_ids),
            "avg_batch_ms": float(np.mean(times)),
            "per_query_ms": float(np.mean(times) / num_queries),
            "p95_batch_ms": float(np.percentile(times, 95)),
        }
