"""
ClassPulse AI — GPU / MPS Accelerator Utility

Detects available hardware acceleration (Apple MPS, CUDA, CPU)
and provides helpers for moving tensors between devices.
"""

from __future__ import annotations

import logging
import platform

logger = logging.getLogger(__name__)


def get_device() -> str:
    """
    Return the best available compute device string.
    Priority: MPS (Apple Silicon) > CUDA > CPU
    """
    try:
        import torch

        if torch.backends.mps.is_available() and torch.backends.mps.is_built():
            logger.info("Using MPS (Apple Silicon) acceleration.")
            return "mps"
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            logger.info("Using CUDA: %s", name)
            return "cuda"
    except ImportError:
        pass

    logger.info("Using CPU.")
    return "cpu"


def get_tf_device() -> str:
    """Return a TensorFlow device string."""
    try:
        import tensorflow as tf

        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            logger.info("TensorFlow GPU: %s", gpus[0].name)
            return gpus[0].name

        # Apple Silicon Metal via tensorflow-metal plugin
        metal = tf.config.list_physical_devices("Metal")
        if metal:
            logger.info("TensorFlow Metal (Apple Silicon).")
            return metal[0].name
    except Exception:
        pass

    logger.info("TensorFlow using CPU.")
    return "/device:CPU:0"


def system_info() -> dict[str, str]:
    """Collect system information for diagnostics."""
    info: dict[str, str] = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "machine": platform.machine(),
    }

    try:
        import torch
        info["torch"] = torch.__version__
        info["torch_device"] = get_device()
        if hasattr(torch.backends, "mps"):
            info["mps_available"] = str(torch.backends.mps.is_available())
        if torch.cuda.is_available():
            info["cuda_device"] = torch.cuda.get_device_name(0)
    except ImportError:
        info["torch"] = "not installed"

    try:
        import tensorflow as tf
        info["tensorflow"] = tf.__version__
    except ImportError:
        info["tensorflow"] = "not installed"

    try:
        import cv2
        info["opencv"] = cv2.__version__
    except ImportError:
        info["opencv"] = "not installed"

    return info
