"""
ClassPulse AI — Model Validation & Benchmarking

Loads both trained models (emotion + face recognition) and runs
comprehensive evaluation:

  1. Emotion model: accuracy / precision / recall / F1 + confusion matrix
  2. Face recognition: top-1 accuracy + confidence distribution
  3. Inference benchmarks: per-face latency for 60 simultaneous students
  4. Pass/fail against latency targets

Usage
─────
    python -m training.validate_models \
        --emotion_checkpoint ./models/emotion_efficientnetb3_best.pth \
        --face_embeddings ./models/face_embeddings.pkl \
        --emotion_test_dir ./data/emotions/val \
        --face_photos_dir ./data/students \
        --benchmark_faces 60
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("validate")

SEED = 42

# Latency targets (milliseconds)
TARGET_FACE_RECOG_MS = 50
TARGET_EMOTION_MS = 15


def seed_everything(seed: int = SEED):
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


# ── Emotion Model Evaluation ────────────────────────────────

def validate_emotion_model(checkpoint_path: str, test_dir: str) -> dict:
    """
    Load the EfficientNetB3 emotion model and evaluate on the test set.
    Returns a metrics dict.
    """
    import torch
    from torchvision import datasets, transforms

    logger.info("═" * 60)
    logger.info("  Emotion Model Validation")
    logger.info("═" * 60)

    # Device
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
    logger.info("Device: %s", device)

    # Load checkpoint
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    class_names = ckpt["class_names"]
    config = ckpt.get("config", {})
    num_classes = config.get("num_classes", 5)
    img_size = config.get("input_size", 224)

    logger.info("Checkpoint: %s", checkpoint_path)
    logger.info("Best val acc at training: %.2f%%", ckpt.get("val_acc", 0))
    logger.info("Classes: %s", class_names)

    # Build model
    from torchvision import models
    import torch.nn as nn

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
    model = model.to(device)
    model.eval()
    logger.info("Model loaded. ✓")

    # Test dataset
    test_tf = transforms.Compose([
        transforms.Resize((img_size, img_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    test_ds = datasets.ImageFolder(test_dir, transform=test_tf)
    test_dl = torch.utils.data.DataLoader(
        test_ds, batch_size=64, shuffle=False, num_workers=4, pin_memory=True,
    )
    logger.info("Test samples: %d", len(test_ds))

    # Inference
    all_preds = []
    all_labels = []
    all_probs = []

    t0 = time.time()
    with torch.no_grad():
        for images, labels in test_dl:
            images = images.to(device)
            outputs = model(images)
            probs = torch.softmax(outputs, dim=1)
            _, preds = outputs.max(1)

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.numpy())
            all_probs.extend(probs.cpu().numpy())

    inference_time = time.time() - t0
    per_sample_ms = (inference_time / len(test_ds)) * 1000

    # Metrics
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        classification_report, confusion_matrix,
    )

    accuracy = accuracy_score(all_labels, all_preds) * 100
    precision = precision_score(all_labels, all_preds, average="weighted") * 100
    recall = recall_score(all_labels, all_preds, average="weighted") * 100
    f1 = f1_score(all_labels, all_preds, average="weighted") * 100

    logger.info("")
    logger.info("Results:")
    logger.info("  Accuracy  : %.2f%%", accuracy)
    logger.info("  Precision : %.2f%%", precision)
    logger.info("  Recall    : %.2f%%", recall)
    logger.info("  F1 Score  : %.2f%%", f1)
    logger.info("  Inference : %.2f ms/sample", per_sample_ms)

    # Classification report
    report_str = classification_report(
        all_labels, all_preds, target_names=class_names, digits=4,
    )
    logger.info("\nClassification Report:\n%s", report_str)

    # Confusion matrix
    cm = confusion_matrix(all_labels, all_preds)
    logger.info("Confusion Matrix:")
    header = "          " + "  ".join(f"{c[:6]:>6}" for c in class_names)
    logger.info(header)
    for i, row in enumerate(cm):
        row_str = f"{class_names[i][:8]:<10}" + "  ".join(f"{v:>6}" for v in row)
        logger.info(row_str)

    # Pass/fail
    logger.info("")
    if accuracy >= 90.0:
        logger.info("✅ Emotion accuracy TARGET MET: %.2f%% ≥ 90%%", accuracy)
    else:
        logger.warning("❌ Emotion accuracy TARGET MISSED: %.2f%% < 90%%", accuracy)

    if per_sample_ms <= TARGET_EMOTION_MS:
        logger.info("✅ Emotion latency TARGET MET: %.2f ms ≤ %d ms", per_sample_ms, TARGET_EMOTION_MS)
    else:
        logger.warning("❌ Emotion latency TARGET MISSED: %.2f ms > %d ms", per_sample_ms, TARGET_EMOTION_MS)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "per_sample_ms": per_sample_ms,
        "confusion_matrix": cm.tolist(),
        "report": classification_report(
            all_labels, all_preds, target_names=class_names, output_dict=True,
        ),
    }


# ── Face Recognition Evaluation ─────────────────────────────

def validate_face_recognition(embeddings_path: str, photos_dir: str) -> dict:
    """
    Load face embeddings and test recognition accuracy using holdout photos.
    """
    import pickle

    logger.info("")
    logger.info("═" * 60)
    logger.info("  Face Recognition Validation")
    logger.info("═" * 60)

    # Load embeddings
    with open(embeddings_path, "rb") as f:
        payload = pickle.load(f)

    embeddings: dict[str, np.ndarray] = payload["embeddings"]
    student_ids = list(embeddings.keys())
    emb_matrix = np.stack([embeddings[sid] for sid in student_ids])

    logger.info("Embeddings loaded: %d students, %d-dim", len(student_ids), payload["embedding_dim"])
    logger.info("Backend: %s", payload.get("model_backend", "unknown"))

    # Load embedder for test photos
    from training.setup_face_recognition import FaceNetEmbedder, scan_photos

    embedder = FaceNetEmbedder()
    student_photos = scan_photos(photos_dir)

    # Test: use last photo of each student as holdout
    correct = 0
    total = 0
    latencies: list[float] = []
    confidences: list[float] = []

    for student_id, photos in student_photos.items():
        if student_id not in embeddings or len(photos) < 2:
            continue

        test_photo = photos[-1]  # holdout

        t0 = time.time()
        query_emb = embedder.embed(test_photo)
        embed_time = (time.time() - t0) * 1000

        if query_emb is None:
            continue

        # Normalize
        query_emb = query_emb / (np.linalg.norm(query_emb) + 1e-8)

        # Cosine similarity (vectorized)
        t0 = time.time()
        similarities = emb_matrix @ query_emb
        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])
        predicted_id = student_ids[best_idx]
        match_time = (time.time() - t0) * 1000

        total_time = embed_time + match_time
        latencies.append(total_time)
        confidences.append(best_sim)

        total += 1
        if predicted_id == student_id:
            correct += 1

    accuracy = (correct / total * 100) if total > 0 else 0.0

    logger.info("")
    logger.info("Results:")
    logger.info("  Test samples       : %d", total)
    logger.info("  Correct matches    : %d", correct)
    logger.info("  Top-1 Accuracy     : %.2f%%", accuracy)

    if latencies:
        avg_latency = np.mean(latencies)
        p95_latency = np.percentile(latencies, 95)
        logger.info("  Avg latency        : %.2f ms", avg_latency)
        logger.info("  P95 latency        : %.2f ms", p95_latency)
        logger.info("  Avg confidence     : %.4f", np.mean(confidences))
        logger.info("  Min confidence     : %.4f", np.min(confidences))

    logger.info("")
    if accuracy >= 90.0:
        logger.info("✅ Face recognition TARGET MET: %.2f%% ≥ 90%%", accuracy)
    else:
        logger.warning("❌ Face recognition TARGET MISSED: %.2f%% < 90%%", accuracy)

    if latencies and np.mean(latencies) <= TARGET_FACE_RECOG_MS:
        logger.info("✅ Face recog latency TARGET MET: %.2f ms ≤ %d ms", np.mean(latencies), TARGET_FACE_RECOG_MS)
    elif latencies:
        logger.warning("❌ Face recog latency TARGET MISSED: %.2f ms > %d ms", np.mean(latencies), TARGET_FACE_RECOG_MS)

    return {
        "accuracy": accuracy,
        "total_tested": total,
        "correct": correct,
        "avg_latency_ms": float(np.mean(latencies)) if latencies else 0,
        "p95_latency_ms": float(np.percentile(latencies, 95)) if latencies else 0,
        "avg_confidence": float(np.mean(confidences)) if confidences else 0,
    }


# ── Batch Benchmark (60 faces) ──────────────────────────────

def benchmark_batch_inference(
    emotion_checkpoint: str,
    embeddings_path: str,
    num_faces: int = 60,
) -> dict:
    """
    Simulate processing `num_faces` simultaneously and report latencies.
    """
    import pickle
    import torch
    from torchvision import models, transforms
    import torch.nn as nn

    logger.info("")
    logger.info("═" * 60)
    logger.info("  Batch Inference Benchmark (%d faces)", num_faces)
    logger.info("═" * 60)

    # Device
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    # ── Emotion model ────────────────────────────────────────
    ckpt = torch.load(emotion_checkpoint, map_location=device, weights_only=False)
    config = ckpt.get("config", {})
    num_classes = config.get("num_classes", 5)

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
    model = model.to(device)
    model.eval()

    # ── Face embeddings ──────────────────────────────────────
    with open(embeddings_path, "rb") as f:
        payload = pickle.load(f)
    emb_matrix = np.stack(list(payload["embeddings"].values()))

    # ── Generate synthetic test data ─────────────────────────
    # Simulate face crops (224×224 RGB)
    fake_crops = np.random.randint(0, 255, (num_faces, 224, 224, 3), dtype=np.uint8)

    # ── Emotion inference benchmark ──────────────────────────
    tf = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # Batch transform
    batch_tensor = torch.stack([tf(crop) for crop in fake_crops]).to(device)

    # Warmup
    with torch.no_grad():
        _ = model(batch_tensor[:4])

    # Benchmark emotion (10 runs)
    emotion_times: list[float] = []
    for _ in range(10):
        t0 = time.time()
        with torch.no_grad():
            _ = model(batch_tensor)
        if device.type == "cuda":
            torch.cuda.synchronize()
        emotion_times.append((time.time() - t0) * 1000)

    avg_emotion_total = np.mean(emotion_times)
    avg_emotion_per_face = avg_emotion_total / num_faces

    logger.info("")
    logger.info("Emotion Detection:")
    logger.info("  Batch (%d faces) : %.2f ms avg", num_faces, avg_emotion_total)
    logger.info("  Per face         : %.2f ms avg", avg_emotion_per_face)

    # ── Face recognition benchmark ───────────────────────────
    # Simulate query embeddings
    fake_embeddings = np.random.randn(num_faces, 512).astype(np.float32)
    fake_embeddings /= np.linalg.norm(fake_embeddings, axis=1, keepdims=True)

    # Warmup
    _ = fake_embeddings[:4] @ emb_matrix.T

    # Benchmark face matching (10 runs)
    face_times: list[float] = []
    for _ in range(10):
        t0 = time.time()
        # Vectorized batch cosine similarity
        similarities = fake_embeddings @ emb_matrix.T  # (60, N_enrolled)
        best_idxs = np.argmax(similarities, axis=1)
        best_sims = similarities[np.arange(num_faces), best_idxs]
        face_times.append((time.time() - t0) * 1000)

    avg_face_total = np.mean(face_times)
    avg_face_per_face = avg_face_total / num_faces

    logger.info("")
    logger.info("Face Recognition (matching only, excl. embedding extraction):")
    logger.info("  Batch (%d faces) : %.2f ms avg", num_faces, avg_face_total)
    logger.info("  Per face         : %.4f ms avg", avg_face_per_face)

    # ── Combined pipeline ────────────────────────────────────
    total_per_face = avg_emotion_per_face + avg_face_per_face
    logger.info("")
    logger.info("Combined Pipeline:")
    logger.info("  Per face         : %.2f ms (emotion) + %.4f ms (matching) = %.2f ms",
                avg_emotion_per_face, avg_face_per_face, total_per_face)

    # ── Pass/fail ────────────────────────────────────────────
    logger.info("")
    if avg_emotion_per_face <= TARGET_EMOTION_MS:
        logger.info("✅ Emotion per-face TARGET MET: %.2f ms ≤ %d ms", avg_emotion_per_face, TARGET_EMOTION_MS)
    else:
        logger.warning("❌ Emotion per-face TARGET MISSED: %.2f ms > %d ms", avg_emotion_per_face, TARGET_EMOTION_MS)

    if avg_face_per_face <= TARGET_FACE_RECOG_MS:
        logger.info("✅ Face recog per-face TARGET MET: %.4f ms ≤ %d ms", avg_face_per_face, TARGET_FACE_RECOG_MS)
    else:
        logger.warning("❌ Face recog per-face TARGET MISSED: %.4f ms > %d ms", avg_face_per_face, TARGET_FACE_RECOG_MS)

    return {
        "num_faces": num_faces,
        "emotion_batch_ms": avg_emotion_total,
        "emotion_per_face_ms": avg_emotion_per_face,
        "face_match_batch_ms": avg_face_total,
        "face_match_per_face_ms": avg_face_per_face,
        "combined_per_face_ms": total_per_face,
    }


# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Validate ClassPulse AI models")
    parser.add_argument("--emotion_checkpoint", type=str, default="./models/emotion_efficientnetb3_best.pth")
    parser.add_argument("--face_embeddings", type=str, default="./models/face_embeddings.pkl")
    parser.add_argument("--emotion_test_dir", type=str, default="./data/emotions/val")
    parser.add_argument("--face_photos_dir", type=str, default="./data/students")
    parser.add_argument("--benchmark_faces", type=int, default=60)
    parser.add_argument("--output", type=str, default="./models/validation_report.json")
    args = parser.parse_args()

    seed_everything()

    logger.info("=" * 60)
    logger.info("  ClassPulse AI — Model Validation Suite")
    logger.info("=" * 60)

    results: dict = {}

    # 1. Emotion model
    if os.path.exists(args.emotion_checkpoint) and os.path.exists(args.emotion_test_dir):
        results["emotion"] = validate_emotion_model(args.emotion_checkpoint, args.emotion_test_dir)
    else:
        logger.warning("⚠ Skipping emotion validation (missing checkpoint or test dir)")

    # 2. Face recognition
    if os.path.exists(args.face_embeddings) and os.path.exists(args.face_photos_dir):
        results["face_recognition"] = validate_face_recognition(args.face_embeddings, args.face_photos_dir)
    else:
        logger.warning("⚠ Skipping face recognition validation (missing embeddings or photos)")

    # 3. Batch benchmark
    if os.path.exists(args.emotion_checkpoint) and os.path.exists(args.face_embeddings):
        results["benchmark"] = benchmark_batch_inference(
            args.emotion_checkpoint, args.face_embeddings, args.benchmark_faces
        )
    else:
        logger.warning("⚠ Skipping benchmark (missing model files)")

    # ── Summary ──────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("  Validation Summary")
    logger.info("=" * 60)

    all_pass = True

    if "emotion" in results:
        em = results["emotion"]
        emo_acc_pass = em["accuracy"] >= 90.0
        emo_lat_pass = em["per_sample_ms"] <= TARGET_EMOTION_MS
        logger.info("  Emotion accuracy   : %.2f%%  %s", em["accuracy"], "✅" if emo_acc_pass else "❌")
        logger.info("  Emotion latency    : %.2f ms %s", em["per_sample_ms"], "✅" if emo_lat_pass else "❌")
        all_pass = all_pass and emo_acc_pass and emo_lat_pass

    if "face_recognition" in results:
        fr = results["face_recognition"]
        fr_acc_pass = fr["accuracy"] >= 90.0
        fr_lat_pass = fr["avg_latency_ms"] <= TARGET_FACE_RECOG_MS
        logger.info("  Face recog acc     : %.2f%%  %s", fr["accuracy"], "✅" if fr_acc_pass else "❌")
        logger.info("  Face recog latency : %.2f ms %s", fr["avg_latency_ms"], "✅" if fr_lat_pass else "❌")
        all_pass = all_pass and fr_acc_pass and fr_lat_pass

    if "benchmark" in results:
        bm = results["benchmark"]
        logger.info("  60-face batch      : %.2f ms total", bm["emotion_batch_ms"] + bm["face_match_batch_ms"])

    logger.info("")
    if all_pass:
        logger.info("🎉 ALL TARGETS MET — models ready for production!")
    else:
        logger.warning("⚠ SOME TARGETS MISSED — review details above.")

    # Save report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Report saved: %s", output_path)
    logger.info("Done. 🚀")


if __name__ == "__main__":
    main()
