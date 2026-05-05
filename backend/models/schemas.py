"""
ClassPulse AI — Pydantic schemas for all API request/response types.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────

class EmotionLabel(str, Enum):
    attentive = "attentive"
    distracted = "distracted"
    sleepy = "sleepy"
    confused = "confused"
    engaged = "engaged"


class AlertType(str, Enum):
    phone_detected = "phone_detected"
    low_engagement = "low_engagement"
    mass_sleeping = "mass_sleeping"
    high_confusion = "high_confusion"
    attendance_anomaly = "attendance_anomaly"


class AlertSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AttendanceStatus(str, Enum):
    present = "present"
    absent = "absent"
    late = "late"


class SessionStatus(str, Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


# ── Detection results ────────────────────────────────────────

class BoundingBox(BaseModel):
    """Normalised bounding box [0-1]."""
    x: float
    y: float
    w: float
    h: float


class FaceLandmarks(BaseModel):
    """Key facial landmarks from MediaPipe."""
    left_eye: tuple[float, float] = (0.0, 0.0)
    right_eye: tuple[float, float] = (0.0, 0.0)
    nose_tip: tuple[float, float] = (0.0, 0.0)
    mouth_center: tuple[float, float] = (0.0, 0.0)
    left_ear: tuple[float, float] = (0.0, 0.0)
    right_ear: tuple[float, float] = (0.0, 0.0)


class FaceDetection(BaseModel):
    """A single detected face in a frame."""
    id: int = Field(description="Temporary per-frame ID")
    bbox: BoundingBox
    landmarks: FaceLandmarks
    confidence: float = Field(ge=0.0, le=1.0)


class StudentDetection(BaseModel):
    """Detected and recognised student."""
    track_id: int
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    bbox: BoundingBox
    confidence: float = Field(ge=0.0, le=1.0)
    emotion: Optional[EmotionLabel] = None
    emotion_confidence: Optional[float] = None
    engagement_score: Optional[float] = None
    has_phone: bool = False


class EmotionResult(BaseModel):
    """Emotion classification for a student."""
    student_id: Optional[str] = None
    track_id: int
    emotion: EmotionLabel
    confidence: float = Field(ge=0.0, le=1.0)
    raw_scores: dict[str, float] = Field(default_factory=dict)


class PhoneDetection(BaseModel):
    """Detected mobile phone."""
    bbox: BoundingBox
    confidence: float = Field(ge=0.0, le=1.0)
    nearby_student_id: Optional[str] = None
    nearby_track_id: Optional[int] = None


class EngagementScore(BaseModel):
    """Per-student engagement calculation."""
    student_id: Optional[str] = None
    track_id: int
    score: float = Field(ge=0.0, le=100.0)
    attention: float = Field(ge=0.0, le=1.0)
    emotion_positive: float = Field(ge=0.0, le=1.0)
    posture: float = Field(ge=0.0, le=1.0)
    presence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TrackInfo(BaseModel):
    """Persistent tracker data for a person."""
    track_id: int
    bbox: BoundingBox
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    frames_since_recognition: int = 0


# ── Alerts ───────────────────────────────────────────────────

class AlertPayload(BaseModel):
    """Alert triggered by the AI pipeline."""
    type: AlertType
    message: str
    severity: AlertSeverity
    student_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Session & metrics ────────────────────────────────────────

class SessionMetrics(BaseModel):
    """Aggregated metrics for a live session."""
    session_id: str
    total_students: int = 0
    present_students: int = 0
    avg_engagement: float = 0.0
    emotion_distribution: dict[str, int] = Field(default_factory=dict)
    phone_detections: int = 0
    alerts_count: int = 0
    fps: float = 0.0
    latency_ms: float = 0.0
    detection_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FrameResult(BaseModel):
    """Complete result of processing a single frame."""
    frame_number: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    detections: list[StudentDetection] = Field(default_factory=list)
    phone_detections: list[PhoneDetection] = Field(default_factory=list)
    alerts: list[AlertPayload] = Field(default_factory=list)
    metrics: Optional[SessionMetrics] = None
    processing_time_ms: float = 0.0


# ── Reports ──────────────────────────────────────────────────

class ReportRequest(BaseModel):
    """Request body to generate an AI report."""
    session_id: str
    teacher_id: str
    include_student_highlights: bool = True
    include_recommendations: bool = True


class ReportInsight(BaseModel):
    """A single insight from an AI report."""
    title: str
    description: str
    metric: Optional[str] = None
    icon: Optional[str] = None


class StudentHighlight(BaseModel):
    """Per-student highlight in a report."""
    student_id: str
    student_name: str
    avg_engagement: float
    dominant_emotion: str
    attendance_status: str
    notes: str


class ReportResponse(BaseModel):
    """Generated AI report."""
    id: str
    session_id: str
    title: str
    summary: str
    key_insights: list[ReportInsight] = Field(default_factory=list)
    student_highlights: list[StudentHighlight] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    metrics_snapshot: dict = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    pdf_url: Optional[str] = None


# ── WebSocket payloads ───────────────────────────────────────

class WSMessage(BaseModel):
    """Standard WebSocket message wrapper."""
    type: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Health ───────────────────────────────────────────────────

class HealthCheck(BaseModel):
    """Health-check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    models_loaded: dict[str, bool] = Field(default_factory=dict)
    uptime_seconds: float = 0.0
