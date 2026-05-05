"""
ClassPulse AI — Backend Configuration

Centralised settings loaded from environment variables via pydantic-settings.
Supports production (Railway/Render) and local development.
"""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide configuration sourced from .env."""

    # ── App ──────────────────────────────────────────────────
    app_name: str = "ClassPulse AI"
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8000, alias="PORT")

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=lambda: _build_cors_origins())

    # ── Supabase ─────────────────────────────────────────────
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ── Upstash (used when UPSTASH_REDIS_REST_URL is set) ────
    upstash_redis_url: str = Field(default="", alias="UPSTASH_REDIS_REST_URL")
    upstash_redis_token: str = Field(default="", alias="UPSTASH_REDIS_REST_TOKEN")

    # ── Camera ───────────────────────────────────────────────
    camera_source: int | str = Field(default=0, alias="CAMERA_SOURCE")
    capture_width: int = 3840
    capture_height: int = 2160
    process_width: int = 1920
    process_height: int = 1080
    capture_fps: int = 30
    frame_buffer_size: int = 5

    # ── Face Detection (MediaPipe) ───────────────────────────
    face_detection_confidence: float = 0.70
    face_detection_model: int = 1  # 0=short-range, 1=long-range

    # ── Face Recognition (DeepFace + FaceNet512) ─────────────
    recognition_model: str = "Facenet512"
    recognition_threshold: float = 0.68
    recognition_interval: int = 30  # re-recognize every N frames

    # ── Emotion Detection ────────────────────────────────────
    emotion_classes: list[str] = [
        "attentive", "distracted", "sleepy", "confused", "engaged",
    ]
    emotion_confidence_threshold: float = 0.65
    emotion_smoothing_window: int = 5

    # ── Phone Detection (YOLOv8) ─────────────────────────────
    yolo_model_path: str = Field(default="yolov8x.pt", alias="YOLO_MODEL_PATH")
    yolo_confidence: float = 0.72
    yolo_nms_threshold: float = 0.45

    # ── Model Paths ──────────────────────────────────────────
    model_path: str = Field(default="./models", alias="MODEL_PATH")
    emotion_model_path: str = ""  # defaults to {model_path}/emotion_efficientnetb3_best.pth
    face_embeddings_path: str = ""  # defaults to {model_path}/face_embeddings.pkl

    # ── Engagement Scoring ───────────────────────────────────
    engagement_calc_interval: float = 2.0   # seconds
    engagement_push_interval: float = 10.0  # seconds
    weight_attention: float = 0.4
    weight_emotion: float = 0.3
    weight_posture: float = 0.2
    weight_presence: float = 0.1

    # ── Tracking (DeepSORT) ──────────────────────────────────
    tracker_max_age: int = 30
    tracker_n_init: int = 3

    # ── Report Generation ────────────────────────────────────
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    report_model: str = "claude-sonnet-4-20250514"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "extra": "ignore",
    }

    # ── Computed properties ──────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def effective_emotion_model_path(self) -> str:
        if self.emotion_model_path:
            return self.emotion_model_path
        return os.path.join(self.model_path, "emotion_efficientnetb3_best.pth")

    @property
    def effective_face_embeddings_path(self) -> str:
        if self.face_embeddings_path:
            return self.face_embeddings_path
        return os.path.join(self.model_path, "face_embeddings.pkl")


def _build_cors_origins() -> list[str]:
    """
    Build CORS origins list with Vercel URL auto-detection.

    In production:
      - Main Vercel domain (VERCEL_PROJECT_PRODUCTION_URL)
      - Preview deployment URLs
      - Custom domain (FRONTEND_URL)

    Always includes:
      - http://localhost:3000 (local dev)
    """
    origins = ["http://localhost:3000"]

    # Vercel production URL
    vercel_url = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")
    if vercel_url:
        origins.append(f"https://{vercel_url}")

    # Vercel preview URLs (branch-based)
    vercel_branch_url = os.environ.get("VERCEL_BRANCH_URL")
    if vercel_branch_url:
        origins.append(f"https://{vercel_branch_url}")

    # Vercel deployment URL (unique per deploy)
    vercel_deploy_url = os.environ.get("VERCEL_URL")
    if vercel_deploy_url:
        origins.append(f"https://{vercel_deploy_url}")

    # Custom frontend URL
    frontend_url = os.environ.get("FRONTEND_URL")
    if frontend_url:
        origins.append(frontend_url)

    # Hard-coded production domain
    origins.append("https://classpulse-ai.vercel.app")

    return list(set(origins))  # deduplicate


settings = Settings()
