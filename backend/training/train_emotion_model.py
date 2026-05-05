"""
ClassPulse AI — Emotion Detection Model Training Pipeline

Transfer-learns EfficientNetB3 on FER2013 + AffectNet for classroom emotion
classification.  Five output classes:

    attentive · distracted · sleepy · confused · engaged

Target: ≥ 90 % validation accuracy.

Usage
─────
    python -m training.train_emotion_model \
        --data_dir ./data/emotions \
        --output_dir ./models \
        --epochs 50 \
        --batch_size 64

Data directory layout expected:

    data/emotions/
    ├── train/
    │   ├── attentive/   *.jpg
    │   ├── distracted/
    │   ├── sleepy/
    │   ├── confused/
    │   └── engaged/
    └── val/
        ├── attentive/
        ├── distracted/
        ├── sleepy/
        ├── confused/
        └── engaged/

Hardware: Apple M-series (MPS) · NVIDIA CUDA · CPU fallback.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.amp import GradScaler, autocast
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from torchvision import datasets, models, transforms

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_emotion")

# ── Constants ────────────────────────────────────────────────

CLASSES = ["attentive", "confused", "distracted", "engaged", "sleepy"]
NUM_CLASSES = len(CLASSES)
IMG_SIZE = 224  # EfficientNetB3 native input
SEED = 42


# ── Reproducibility ─────────────────────────────────────────

def seed_everything(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ["PYTHONHASHSEED"] = str(seed)


# ── Device selection ─────────────────────────────────────────

def get_device() -> torch.device:
    if torch.cuda.is_available():
        dev = torch.device("cuda")
        logger.info("Using CUDA: %s", torch.cuda.get_device_name(0))
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        dev = torch.device("mps")
        logger.info("Using Apple MPS acceleration.")
    else:
        dev = torch.device("cpu")
        logger.info("Using CPU (no GPU detected).")
    return dev


# ── Label-smoothing cross entropy ────────────────────────────

class LabelSmoothingCrossEntropy(nn.Module):
    """Cross-entropy with optional label smoothing."""

    def __init__(self, smoothing: float = 0.1):
        super().__init__()
        self.smoothing = smoothing
        self.confidence = 1.0 - smoothing

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        log_probs = torch.log_softmax(pred, dim=-1)
        nll_loss = -log_probs.gather(dim=-1, index=target.unsqueeze(1)).squeeze(1)
        smooth_loss = -log_probs.mean(dim=-1)
        return (self.confidence * nll_loss + self.smoothing * smooth_loss).mean()


# ── Data loaders ─────────────────────────────────────────────

def build_transforms():
    """Training augmentation + validation normalisation."""
    train_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2, hue=0.05),
        transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
        transforms.RandomGrayscale(p=0.05),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        transforms.RandomErasing(p=0.15, scale=(0.02, 0.15)),
    ])

    val_tf = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    return train_tf, val_tf


def build_dataloaders(
    data_dir: str, batch_size: int, num_workers: int = 4
) -> tuple[DataLoader, DataLoader, list[str]]:
    train_tf, val_tf = build_transforms()

    train_ds = datasets.ImageFolder(os.path.join(data_dir, "train"), transform=train_tf)
    val_ds = datasets.ImageFolder(os.path.join(data_dir, "val"), transform=val_tf)

    class_names = train_ds.classes
    assert class_names == CLASSES, (
        f"Expected classes {CLASSES}, got {class_names}. "
        "Rename folders to match the expected class names."
    )

    logger.info("Training samples  : %d", len(train_ds))
    logger.info("Validation samples: %d", len(val_ds))
    logger.info("Classes           : %s", class_names)

    # Compute class weights for imbalanced datasets
    class_counts = np.bincount([s[1] for s in train_ds.samples], minlength=NUM_CLASSES)
    class_weights = 1.0 / (class_counts + 1e-6)
    class_weights = class_weights / class_weights.sum() * NUM_CLASSES
    logger.info("Class distribution: %s", dict(zip(class_names, class_counts)))
    logger.info("Class weights     : %s", dict(zip(class_names, np.round(class_weights, 3))))

    # Weighted sampler for balanced batches
    sample_weights = [class_weights[s[1]] for s in train_ds.samples]
    sampler = torch.utils.data.WeightedRandomSampler(
        weights=sample_weights,
        num_samples=len(train_ds),
        replacement=True,
    )

    train_dl = DataLoader(
        train_ds, batch_size=batch_size, sampler=sampler,
        num_workers=num_workers, pin_memory=True, drop_last=True,
    )
    val_dl = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True,
    )

    return train_dl, val_dl, class_names


# ── Model ────────────────────────────────────────────────────

def build_model(num_classes: int = NUM_CLASSES, dropout: float = 0.4) -> nn.Module:
    """
    EfficientNetB3 with a custom classification head.

    Strategy:
      - Freeze the convolutional backbone initially
      - Replace the classifier head with:
            Dropout → Linear(1536, 512) → ReLU → BN → Dropout → Linear(512, num_classes)
    """
    model = models.efficientnet_b3(weights=models.EfficientNet_B3_Weights.DEFAULT)

    # Freeze backbone
    for param in model.features.parameters():
        param.requires_grad = False

    # Custom head
    in_features = model.classifier[1].in_features  # 1536
    model.classifier = nn.Sequential(
        nn.Dropout(p=dropout),
        nn.Linear(in_features, 512),
        nn.ReLU(inplace=True),
        nn.BatchNorm1d(512),
        nn.Dropout(p=dropout * 0.5),
        nn.Linear(512, num_classes),
    )

    return model


def unfreeze_backbone(model: nn.Module, lr: float) -> list[dict]:
    """Unfreeze backbone layers with a lower learning rate (discriminative LR)."""
    for param in model.features.parameters():
        param.requires_grad = True

    param_groups = [
        {"params": model.features.parameters(), "lr": lr * 0.1},  # backbone — slower
        {"params": model.classifier.parameters(), "lr": lr},       # head — normal
    ]
    logger.info("🔓 Backbone unfrozen with discriminative LR (backbone=%.1e, head=%.1e)", lr * 0.1, lr)
    return param_groups


# ── Training loop ────────────────────────────────────────────

def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    scaler: Optional[GradScaler],
    device: torch.device,
    max_grad_norm: float = 1.0,
) -> tuple[float, float]:
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    amp_device_type = "cuda" if device.type == "cuda" else "cpu"
    use_amp = device.type == "cuda"

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad(set_to_none=True)

        if use_amp and scaler is not None:
            with autocast(device_type=amp_device_type):
                outputs = model(images)
                loss = criterion(outputs, labels)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm)
            optimizer.step()

        running_loss += loss.item() * images.size(0)
        _, preds = outputs.max(1)
        correct += preds.eq(labels).sum().item()
        total += labels.size(0)

    epoch_loss = running_loss / total
    epoch_acc = correct / total * 100
    return epoch_loss, epoch_acc


@torch.no_grad()
def validate(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float, list, list]:
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0
    all_preds = []
    all_labels = []

    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        outputs = model(images)
        loss = criterion(outputs, labels)

        running_loss += loss.item() * images.size(0)
        _, preds = outputs.max(1)
        correct += preds.eq(labels).sum().item()
        total += labels.size(0)
        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(labels.cpu().numpy())

    epoch_loss = running_loss / total
    epoch_acc = correct / total * 100
    return epoch_loss, epoch_acc, all_preds, all_labels


# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train ClassPulse emotion model")
    parser.add_argument("--data_dir", type=str, default="./data/emotions")
    parser.add_argument("--output_dir", type=str, default="./models")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--unfreeze_epoch", type=int, default=5,
                        help="Epoch at which to unfreeze the backbone")
    parser.add_argument("--label_smoothing", type=float, default=0.1)
    parser.add_argument("--num_workers", type=int, default=4)
    args = parser.parse_args()

    seed_everything()
    device = get_device()

    # Directories
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "runs" / f"emotion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info("=" * 64)
    logger.info("  ClassPulse AI — Emotion Model Training")
    logger.info("=" * 64)
    logger.info("Data dir      : %s", args.data_dir)
    logger.info("Output dir    : %s", args.output_dir)
    logger.info("Epochs        : %d", args.epochs)
    logger.info("Batch size    : %d", args.batch_size)
    logger.info("Learning rate : %.1e", args.lr)
    logger.info("Label smooth  : %.2f", args.label_smoothing)
    logger.info("Device        : %s", device)
    logger.info("-" * 64)

    # Data
    train_dl, val_dl, class_names = build_dataloaders(
        args.data_dir, args.batch_size, args.num_workers
    )

    # Model
    model = build_model().to(device)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info("Model params  : %s total, %s trainable",
                f"{total_params:,}", f"{trainable_params:,}")

    # Loss, optimizer, scheduler
    criterion = LabelSmoothingCrossEntropy(smoothing=args.label_smoothing)
    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr, weight_decay=args.weight_decay,
    )
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-7)
    scaler = GradScaler("cuda") if device.type == "cuda" else None

    # TensorBoard
    writer = SummaryWriter(log_dir=str(log_dir))

    # Training state
    best_val_acc = 0.0
    best_epoch = 0
    epochs_no_improve = 0
    history: dict[str, list] = {
        "train_loss": [], "train_acc": [],
        "val_loss": [], "val_acc": [], "lr": [],
    }

    checkpoint_path = output_dir / "emotion_efficientnetb3_best.pth"

    logger.info("")
    logger.info("%-6s │ %-10s │ %-9s │ %-10s │ %-9s │ %-10s │ %s",
                "Epoch", "Train Loss", "Train Acc", "Val Loss", "Val Acc", "LR", "Status")
    logger.info("─" * 82)

    for epoch in range(1, args.epochs + 1):
        t0 = time.time()

        # Phase 2: unfreeze backbone after N epochs
        if epoch == args.unfreeze_epoch:
            param_groups = unfreeze_backbone(model, args.lr)
            optimizer = optim.AdamW(param_groups, weight_decay=args.weight_decay)
            scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs - epoch, eta_min=1e-7)

        # Train
        train_loss, train_acc = train_one_epoch(
            model, train_dl, criterion, optimizer, scaler, device
        )

        # Validate
        val_loss, val_acc, val_preds, val_labels = validate(
            model, val_dl, criterion, device
        )

        current_lr = optimizer.param_groups[0]["lr"]
        scheduler.step()

        # History
        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)
        history["lr"].append(current_lr)

        # TensorBoard
        writer.add_scalars("Loss", {"train": train_loss, "val": val_loss}, epoch)
        writer.add_scalars("Accuracy", {"train": train_acc, "val": val_acc}, epoch)
        writer.add_scalar("LR", current_lr, epoch)

        # Best model checkpoint
        status = ""
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            epochs_no_improve = 0
            status = f"✓ BEST ({val_acc:.2f}%)"

            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_acc": val_acc,
                "val_loss": val_loss,
                "class_names": class_names,
                "config": {
                    "input_size": IMG_SIZE,
                    "num_classes": NUM_CLASSES,
                    "architecture": "efficientnet_b3",
                    "label_smoothing": args.label_smoothing,
                },
            }, checkpoint_path)
        else:
            epochs_no_improve += 1
            status = f"  (no improve {epochs_no_improve}/{args.patience})"

        elapsed = time.time() - t0
        logger.info(
            "%3d/%-2d │ %10.4f │ %8.2f%% │ %10.4f │ %8.2f%% │ %10.2e │ %s  [%.1fs]",
            epoch, args.epochs, train_loss, train_acc, val_loss, val_acc,
            current_lr, status, elapsed,
        )

        # Early stopping
        if epochs_no_improve >= args.patience:
            logger.info("")
            logger.info("⚠ Early stopping at epoch %d (no improvement for %d epochs).",
                        epoch, args.patience)
            break

    writer.close()

    # ── Final evaluation ─────────────────────────────────────
    logger.info("")
    logger.info("=" * 64)
    logger.info("  Training Complete")
    logger.info("=" * 64)
    logger.info("Best validation accuracy: %.2f%% (epoch %d)", best_val_acc, best_epoch)
    logger.info("Checkpoint saved: %s", checkpoint_path)

    if best_val_acc >= 90.0:
        logger.info("✅ TARGET MET: %.2f%% ≥ 90%%", best_val_acc)
    else:
        logger.warning("⚠ TARGET NOT MET: %.2f%% < 90%%. Consider more data or fine-tuning.", best_val_acc)

    # Classification report
    try:
        from sklearn.metrics import classification_report, confusion_matrix

        # Load best model and re-evaluate
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        _, _, final_preds, final_labels = validate(model, val_dl, criterion, device)

        logger.info("")
        logger.info("Classification Report:")
        logger.info("-" * 64)
        report = classification_report(
            final_labels, final_preds,
            target_names=class_names,
            digits=4,
        )
        logger.info("\n%s", report)

        cm = confusion_matrix(final_labels, final_preds)
        logger.info("Confusion Matrix:")
        logger.info("-" * 64)
        # Header
        header = "          " + "  ".join(f"{c[:6]:>6}" for c in class_names)
        logger.info(header)
        for i, row in enumerate(cm):
            row_str = f"{class_names[i][:8]:<10}" + "  ".join(f"{v:>6}" for v in row)
            logger.info(row_str)

        # Save report
        report_dict = classification_report(
            final_labels, final_preds,
            target_names=class_names,
            output_dict=True,
        )
        report_path = output_dir / "emotion_training_report.json"
        with open(report_path, "w") as f:
            json.dump({
                "best_epoch": best_epoch,
                "best_val_accuracy": best_val_acc,
                "classification_report": report_dict,
                "confusion_matrix": cm.tolist(),
                "history": history,
                "config": vars(args),
            }, f, indent=2, default=str)
        logger.info("Report saved: %s", report_path)

    except ImportError:
        logger.warning("scikit-learn not installed — skipping classification report.")

    logger.info("")
    logger.info("Done. 🚀")


if __name__ == "__main__":
    main()
