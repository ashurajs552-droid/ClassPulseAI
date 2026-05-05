"""
ClassPulse AI — Face Recognition Embedding Setup

Generates 512-dimensional FaceNet embeddings for all enrolled students
and saves them for fast cosine-similarity lookup at inference time.

Usage
─────
    python -m training.setup_face_recognition \
        --photos_dir ./data/students \
        --output ./models/face_embeddings.pkl \
        --test_split 0.2

Photo directory layout:

    data/students/
    ├── STU001/
    │   ├── front.jpg
    │   ├── left.jpg
    │   └── right.jpg
    ├── STU002/
    │   ├── front.jpg
    │   └── ...
    └── ...

Each subfolder name = student_id.
Multiple photos per student → averaged embedding (more robust).

Dependencies: deepface, facenet-pytorch, opencv-python, scikit-learn
"""

from __future__ import annotations

import argparse
import logging
import os
import pickle
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("setup_face")

SEED = 42
EMBEDDING_DIM = 512
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def seed_everything(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


# ── Embedding generator ─────────────────────────────────────

class FaceNetEmbedder:
    """
    Wraps facenet-pytorch's InceptionResnetV1 (pretrained on VGGFace2)
    to produce 512-d face embeddings.

    Falls back to DeepFace with FaceNet512 if facenet-pytorch unavailable.
    """

    def __init__(self) -> None:
        self.model = None
        self.mtcnn = None
        self._backend = "none"
        self._load()

    def _load(self) -> None:
        try:
            from facenet_pytorch import InceptionResnetV1, MTCNN
            import torch

            device = (
                torch.device("mps")
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
                else torch.device("cuda" if torch.cuda.is_available() else "cpu")
            )

            self.mtcnn = MTCNN(
                image_size=160,
                margin=20,
                min_face_size=40,
                thresholds=[0.6, 0.7, 0.7],
                keep_all=False,
                device=device,
            )
            self.model = InceptionResnetV1(pretrained="vggface2").eval().to(device)
            self._device = device
            self._backend = "facenet_pytorch"
            logger.info("✓ Loaded facenet-pytorch InceptionResnetV1 (VGGFace2) on %s", device)
        except ImportError:
            logger.info("facenet-pytorch not found, trying DeepFace …")
            try:
                from deepface import DeepFace
                # Pre-warm the model
                DeepFace.build_model("Facenet512")
                self._backend = "deepface"
                logger.info("✓ Loaded DeepFace FaceNet512 backend.")
            except ImportError:
                logger.error("Neither facenet-pytorch nor deepface installed!")
                sys.exit(1)

    def embed(self, image_path: str) -> Optional[np.ndarray]:
        """
        Generate a 512-dim embedding from an image file.
        Returns None if no face is detected.
        """
        if self._backend == "facenet_pytorch":
            return self._embed_facenet_pytorch(image_path)
        else:
            return self._embed_deepface(image_path)

    def _embed_facenet_pytorch(self, image_path: str) -> Optional[np.ndarray]:
        import torch
        from PIL import Image

        try:
            img = Image.open(image_path).convert("RGB")
            face_tensor = self.mtcnn(img)
            if face_tensor is None:
                return None
            face_tensor = face_tensor.unsqueeze(0).to(self._device)
            with torch.no_grad():
                embedding = self.model(face_tensor)
            return embedding.cpu().numpy().flatten()
        except Exception as e:
            logger.warning("Failed to embed %s: %s", image_path, e)
            return None

    def _embed_deepface(self, image_path: str) -> Optional[np.ndarray]:
        from deepface import DeepFace

        try:
            results = DeepFace.represent(
                img_path=image_path,
                model_name="Facenet512",
                enforce_detection=True,
                detector_backend="mediapipe",
            )
            if results and len(results) > 0:
                return np.array(results[0]["embedding"], dtype=np.float32)
            return None
        except Exception as e:
            logger.warning("Failed to embed %s: %s", image_path, e)
            return None


# ── Photo scanner ────────────────────────────────────────────

def scan_photos(photos_dir: str) -> dict[str, list[str]]:
    """Scan directory for student photos. Returns {student_id: [paths]}."""
    student_photos: dict[str, list[str]] = defaultdict(list)
    root = Path(photos_dir)

    if not root.exists():
        logger.error("Photos directory does not exist: %s", photos_dir)
        sys.exit(1)

    for student_dir in sorted(root.iterdir()):
        if not student_dir.is_dir():
            continue
        student_id = student_dir.name
        for photo in sorted(student_dir.iterdir()):
            if photo.suffix.lower() in SUPPORTED_EXTS:
                student_photos[student_id].append(str(photo))

    logger.info("Found %d students with %d total photos.",
                len(student_photos),
                sum(len(v) for v in student_photos.values()))

    return dict(student_photos)


# ── Embedding pipeline ──────────────────────────────────────

def generate_embeddings(
    student_photos: dict[str, list[str]],
    embedder: FaceNetEmbedder,
) -> dict[str, np.ndarray]:
    """
    Generate averaged 512-d embeddings for each student.
    Multiple photos per student → L2-normalized mean embedding.
    """
    embeddings: dict[str, np.ndarray] = {}
    failed_students: list[str] = []

    for idx, (student_id, photos) in enumerate(student_photos.items(), 1):
        student_embeds: list[np.ndarray] = []

        for photo_path in photos:
            emb = embedder.embed(photo_path)
            if emb is not None:
                # L2 normalize individual embedding
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                student_embeds.append(emb)

        if student_embeds:
            # Average and re-normalize
            avg_embedding = np.mean(student_embeds, axis=0)
            avg_embedding = avg_embedding / np.linalg.norm(avg_embedding)
            embeddings[student_id] = avg_embedding.astype(np.float32)

            logger.info(
                "  [%d/%d] %s: %d/%d photos embedded ✓",
                idx, len(student_photos), student_id,
                len(student_embeds), len(photos),
            )
        else:
            failed_students.append(student_id)
            logger.warning(
                "  [%d/%d] %s: NO FACES DETECTED in any photo ✗",
                idx, len(student_photos), student_id,
            )

    if failed_students:
        logger.warning("")
        logger.warning("⚠ %d students had NO successful embeddings:", len(failed_students))
        for sid in failed_students:
            logger.warning("   - %s", sid)

    return embeddings


# ── Recognition accuracy test ────────────────────────────────

def test_recognition_accuracy(
    embeddings: dict[str, np.ndarray],
    student_photos: dict[str, list[str]],
    embedder: FaceNetEmbedder,
    test_split: float = 0.2,
) -> float:
    """
    Hold out some photos, embed them, and check if cosine similarity
    correctly identifies the student. Reports top-1 accuracy.
    """
    logger.info("")
    logger.info("─" * 50)
    logger.info("Recognition Accuracy Test (%.0f%% holdout)", test_split * 100)
    logger.info("─" * 50)

    if not embeddings:
        logger.warning("No embeddings to test.")
        return 0.0

    # Build test set
    test_pairs: list[tuple[str, str]] = []  # (student_id, photo_path)
    for student_id, photos in student_photos.items():
        if student_id not in embeddings:
            continue
        n_test = max(1, int(len(photos) * test_split))
        # Use last N photos as test (deterministic split)
        test_photos = photos[-n_test:]
        for p in test_photos:
            test_pairs.append((student_id, p))

    if not test_pairs:
        logger.warning("No test photos available.")
        return 0.0

    # Build embedding matrix for vectorized cosine similarity
    student_ids = list(embeddings.keys())
    emb_matrix = np.stack([embeddings[sid] for sid in student_ids])  # (N, 512)

    correct = 0
    total = 0
    confidences: list[float] = []

    for true_id, photo_path in test_pairs:
        query_emb = embedder.embed(photo_path)
        if query_emb is None:
            continue

        # L2 normalize
        query_emb = query_emb / (np.linalg.norm(query_emb) + 1e-8)

        # Cosine similarity
        similarities = emb_matrix @ query_emb  # (N,)
        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])
        predicted_id = student_ids[best_idx]

        total += 1
        if predicted_id == true_id:
            correct += 1
            confidences.append(best_sim)

    accuracy = (correct / total * 100) if total > 0 else 0.0

    logger.info("Test samples     : %d", total)
    logger.info("Correct matches  : %d", correct)
    logger.info("Top-1 Accuracy   : %.2f%%", accuracy)

    if confidences:
        logger.info("Avg confidence   : %.4f", np.mean(confidences))
        logger.info("Min confidence   : %.4f", np.min(confidences))

    if accuracy >= 90.0:
        logger.info("✅ TARGET MET: %.2f%% ≥ 90%%", accuracy)
    else:
        logger.warning("⚠ TARGET NOT MET: %.2f%% < 90%%. Add more / better photos.", accuracy)

    return accuracy


# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Setup face recognition embeddings")
    parser.add_argument("--photos_dir", type=str, default="./data/students")
    parser.add_argument("--output", type=str, default="./models/face_embeddings.pkl")
    parser.add_argument("--test_split", type=float, default=0.2)
    args = parser.parse_args()

    seed_everything()

    logger.info("=" * 60)
    logger.info("  ClassPulse AI — Face Recognition Setup")
    logger.info("=" * 60)
    logger.info("Photos dir : %s", args.photos_dir)
    logger.info("Output     : %s", args.output)
    logger.info("Test split : %.0f%%", args.test_split * 100)
    logger.info("-" * 60)

    # Initialize embedder
    embedder = FaceNetEmbedder()

    # Scan photos
    student_photos = scan_photos(args.photos_dir)

    if not student_photos:
        logger.error("No student photos found in %s", args.photos_dir)
        sys.exit(1)

    # Generate embeddings
    logger.info("")
    logger.info("Generating %d-dim embeddings …", EMBEDDING_DIM)
    t0 = time.time()
    embeddings = generate_embeddings(student_photos, embedder)
    elapsed = time.time() - t0

    logger.info("")
    logger.info("Generated %d embeddings in %.1fs (%.1f per student).",
                len(embeddings), elapsed, elapsed / max(len(embeddings), 1))

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "embeddings": embeddings,
        "student_ids": list(embeddings.keys()),
        "embedding_dim": EMBEDDING_DIM,
        "model_backend": embedder._backend,
        "num_students": len(embeddings),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with open(output_path, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("Saved embeddings: %s (%.2f MB)", output_path, file_size_mb)

    # Test accuracy
    accuracy = test_recognition_accuracy(
        embeddings, student_photos, embedder, args.test_split
    )

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("  Setup Complete")
    logger.info("=" * 60)
    logger.info("  Students enrolled : %d", len(embeddings))
    logger.info("  Embedding dim     : %d", EMBEDDING_DIM)
    logger.info("  Recognition acc   : %.2f%%", accuracy)
    logger.info("  File              : %s", output_path)
    logger.info("")
    logger.info("Done. 🚀")


if __name__ == "__main__":
    main()
