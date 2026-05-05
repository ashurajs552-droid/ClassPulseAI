"""
ClassPulse AI — Frame Processor (Main Pipeline Orchestrator)

Orchestrates the complete per-frame AI pipeline:
  capture → detect faces → track → recognise → detect emotions →
  detect phones → score engagement → push to DB → broadcast via WebSocket

Profiles each step and logs warnings when latency exceeds thresholds.
Target: < 100 ms total per frame.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Optional

import cv2
import numpy as np

from config import settings
from models.schemas import (
    AlertPayload,
    AlertSeverity,
    AlertType,
    BoundingBox,
    EmotionLabel,
    FrameResult,
    PhoneDetection,
    SessionMetrics,
    StudentDetection,
)
from services.camera_service import CameraService
from services.emotion_detection import EmotionDetectionService
from services.engagement_scorer import EngagementScorerService
from services.face_detection import FaceDetectionService
from services.face_recognition import FaceRecognitionService
from services.phone_detection import PhoneDetectionService
from services.tracking_service import TrackingService

logger = logging.getLogger(__name__)

# Step latency thresholds (ms) — log warning if exceeded
LATENCY_THRESHOLDS = {
    "face_detection": 20,
    "tracking": 15,
    "face_recognition": 50,
    "emotion_detection": 15,
    "phone_detection": 30,
    "engagement": 10,
}


class FrameProcessor:
    """
    Main pipeline orchestrator.

    Consumes frames from CameraService, runs every AI service,
    and produces FrameResult objects for WebSocket broadcast.
    """

    def __init__(
        self,
        camera: CameraService,
        face_detector: FaceDetectionService,
        tracker: TrackingService,
        recogniser: FaceRecognitionService,
        emotion_detector: EmotionDetectionService,
        phone_detector: PhoneDetectionService,
        engagement_scorer: EngagementScorerService,
        supabase_client=None,
    ) -> None:
        self._camera = camera
        self._face_detector = face_detector
        self._tracker = tracker
        self._recogniser = recogniser
        self._emotion = emotion_detector
        self._phone = phone_detector
        self._engagement = engagement_scorer
        self._db = supabase_client

        self._frame_count: int = 0
        self._session_id: Optional[str] = None
        self._running = False

        # Connected WebSocket clients
        self._ws_clients: set = set()

        # Alert dedup (type → last alert time)
        self._last_alert: dict[str, float] = {}
        self._alert_cooldown: float = 30.0  # seconds

    # ── Session control ──────────────────────────────────────

    def set_session(self, session_id: str) -> None:
        """Set the current session ID for DB writes."""
        self._session_id = session_id
        self._frame_count = 0
        self._recogniser.clear_track_cache()
        self._emotion.clear_history()
        self._last_alert.clear()
        logger.info("Pipeline session set: %s", session_id)

    def add_ws_client(self, ws) -> None:
        """Register a WebSocket client for broadcasts."""
        self._ws_clients.add(ws)

    def remove_ws_client(self, ws) -> None:
        """Unregister a WebSocket client."""
        self._ws_clients.discard(ws)

    # ── Main pipeline ────────────────────────────────────────

    async def process_frame(self, frame: np.ndarray) -> FrameResult:
        """
        Run the complete AI pipeline on a single frame.

        Pipeline steps:
            1. Face detection (MediaPipe)
            2. Multi-person tracking (DeepSORT)
            3. Face recognition (FaceNet512) — every N frames per track
            4. Emotion detection (EfficientNetB3)
            5. Phone detection (YOLOv8x)
            6. Engagement scoring
            7. Anomaly/alert detection
            8. DB push (async)
            9. WebSocket broadcast

        Returns a FrameResult with all detection data.
        """
        self._frame_count += 1
        pipeline_start = time.perf_counter()
        timings: dict[str, float] = {}
        alerts: list[AlertPayload] = []

        # ── 1. Face Detection ────────────────────────────────
        t0 = time.perf_counter()
        faces = self._face_detector.detect(frame)
        timings["face_detection"] = (time.perf_counter() - t0) * 1000

        # ── 2. Tracking ──────────────────────────────────────
        t0 = time.perf_counter()
        bboxes = [f.bbox for f in faces]
        confs = [f.confidence for f in faces]
        tracks = self._tracker.update(frame, bboxes, confs)
        timings["tracking"] = (time.perf_counter() - t0) * 1000

        # ── 3. Face Recognition ──────────────────────────────
        t0 = time.perf_counter()
        for track in tracks:
            sid, sname, conf = self._recogniser.recognize(
                FaceDetectionService.crop_face(frame, track.bbox),
                track.track_id,
            )
            if sid:
                track.student_id = sid
                track.student_name = sname
                self._tracker.set_student_for_track(track.track_id, sid, sname or "")
        timings["face_recognition"] = (time.perf_counter() - t0) * 1000

        # ── 4. Emotion Detection ─────────────────────────────
        t0 = time.perf_counter()
        face_crops = [
            FaceDetectionService.crop_face(frame, t.bbox) for t in tracks
        ]
        track_ids = [t.track_id for t in tracks]
        student_ids = [t.student_id for t in tracks]
        emotion_results = self._emotion.detect_batch(face_crops, track_ids, student_ids)
        timings["emotion_detection"] = (time.perf_counter() - t0) * 1000

        # Map emotions back to tracks
        emotion_map: dict[int, tuple[EmotionLabel, float]] = {}
        for er in emotion_results:
            emotion_map[er.track_id] = (er.emotion, er.confidence)

        # ── 5. Phone Detection ───────────────────────────────
        t0 = time.perf_counter()
        student_bboxes = [(t.student_id, t.bbox) for t in tracks]
        phone_dets = self._phone.detect(frame, student_bboxes)
        timings["phone_detection"] = (time.perf_counter() - t0) * 1000

        # Generate phone alerts
        for pd in phone_dets:
            alert = self._create_alert(
                AlertType.phone_detected,
                f"Phone detected near student {pd.nearby_student_id or 'unknown'} "
                f"(confidence: {pd.confidence:.0%})",
                AlertSeverity.medium,
                pd.nearby_student_id,
            )
            if alert:
                alerts.append(alert)

        # ── 6. Engagement Scoring ────────────────────────────
        t0 = time.perf_counter()
        engagement_scores = []
        for track in tracks:
            emo_label = emotion_map.get(track.track_id, (None, 0))[0]
            # Find matching face landmarks
            face_lm = None
            for face in faces:
                if self._bbox_iou(face.bbox, track.bbox) > 0.3:
                    face_lm = face.landmarks
                    break

            score = self._engagement.calculate(
                track_id=track.track_id,
                student_id=track.student_id,
                emotion=emo_label.value if emo_label else None,
                landmarks=face_lm,
                bbox=track.bbox,
            )
            if score:
                engagement_scores.append(score)
        timings["engagement"] = (time.perf_counter() - t0) * 1000

        # ── 7. Anomaly detection ─────────────────────────────
        emo_dist = self._emotion.get_class_distribution()
        avg_eng = self._engagement.get_class_average()
        from services.analytics_service import AnalyticsService
        anomalies = AnalyticsService.detect_anomalies(
            AnalyticsService(), emo_dist, avg_eng
        )
        for anom in anomalies:
            alert = self._create_alert(
                AlertType(anom["type"]),
                anom["message"],
                AlertSeverity(anom["severity"]),
            )
            if alert:
                alerts.append(alert)

        # ── Build student detections ─────────────────────────
        student_detections: list[StudentDetection] = []
        for track in tracks:
            emo, emo_conf = emotion_map.get(track.track_id, (None, None))
            eng = next(
                (s.score for s in engagement_scores if s.track_id == track.track_id),
                None,
            )
            has_phone = any(
                pd.nearby_student_id == track.student_id
                for pd in phone_dets
                if track.student_id
            )

            student_detections.append(StudentDetection(
                track_id=track.track_id,
                student_id=track.student_id,
                student_name=track.student_name,
                bbox=track.bbox,
                confidence=0.9,
                emotion=emo,
                emotion_confidence=emo_conf,
                engagement_score=eng,
                has_phone=has_phone,
            ))

        # ── Metrics ──────────────────────────────────────────
        total_time = (time.perf_counter() - pipeline_start) * 1000
        metrics = SessionMetrics(
            session_id=self._session_id or "",
            total_students=len(tracks),
            present_students=sum(1 for t in tracks if t.student_id),
            avg_engagement=avg_eng,
            emotion_distribution=emo_dist,
            phone_detections=len(phone_dets),
            alerts_count=len(alerts),
            fps=self._camera.fps,
            latency_ms=round(total_time, 1),
            detection_count=len(faces),
        )

        # Log step timings
        for step, ms in timings.items():
            threshold = LATENCY_THRESHOLDS.get(step, 50)
            if ms > threshold:
                logger.warning(
                    "⚠ %s took %.1fms (threshold: %dms)",
                    step, ms, threshold,
                )

        if total_time > 100:
            logger.warning("⚠ Total pipeline: %.1fms (target: <100ms)", total_time)

        result = FrameResult(
            frame_number=self._frame_count,
            detections=student_detections,
            phone_detections=phone_dets,
            alerts=alerts,
            metrics=metrics,
            processing_time_ms=round(total_time, 1),
        )

        # ── 8. Async DB push ─────────────────────────────────
        if self._session_id and self._db:
            asyncio.create_task(self._push_to_db(result, engagement_scores, alerts))

        # ── 9. WebSocket broadcast ───────────────────────────
        asyncio.create_task(self._broadcast(result))

        return result

    # ── DB push ──────────────────────────────────────────────

    async def _push_to_db(
        self,
        result: FrameResult,
        engagement_scores: list,
        alerts: list[AlertPayload],
    ) -> None:
        """Push pending scores and alerts to Supabase (fire-and-forget)."""
        try:
            # Engagement scores (batched at interval)
            pending = self._engagement.get_pending_scores()
            if pending and self._session_id:
                rows = [
                    {
                        "session_id": self._session_id,
                        "student_id": s.student_id,
                        "score": s.score,
                        "attention_level": s.attention,
                        "posture_score": s.posture,
                        "emotion_score": s.emotion_positive,
                        "timestamp": s.timestamp.isoformat(),
                    }
                    for s in pending
                    if s.student_id
                ]
                if rows:
                    self._db.table("engagement_scores").insert(rows).execute()

            # Alerts
            if alerts and self._session_id:
                alert_rows = [
                    {
                        "session_id": self._session_id,
                        "type": a.type.value,
                        "message": a.message,
                        "severity": a.severity.value,
                        "student_id": a.student_id,
                        "is_resolved": False,
                    }
                    for a in alerts
                ]
                self._db.table("alerts").insert(alert_rows).execute()

            # Emotion logs (sample every 10th frame)
            if self._frame_count % 10 == 0 and result.detections and self._session_id:
                emo_rows = [
                    {
                        "session_id": self._session_id,
                        "student_id": d.student_id,
                        "emotion": d.emotion.value if d.emotion else "distracted",
                        "confidence": d.emotion_confidence or 0.0,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    for d in result.detections
                    if d.student_id and d.emotion
                ]
                if emo_rows:
                    self._db.table("emotion_logs").insert(emo_rows).execute()

        except Exception as exc:
            logger.error("DB push failed: %s", exc)

    # ── WebSocket broadcast ──────────────────────────────────

    async def _broadcast(self, result: FrameResult) -> None:
        """Broadcast frame result to all connected WebSocket clients."""
        if not self._ws_clients:
            return

        payload = {
            "type": "frame_update",
            "data": {
                "frame_number": result.frame_number,
                "detections": [d.model_dump() for d in result.detections],
                "phone_detections": [p.model_dump() for p in result.phone_detections],
                "alerts": [a.model_dump(mode="json") for a in result.alerts],
                "metrics": result.metrics.model_dump(mode="json") if result.metrics else None,
                "processing_time_ms": result.processing_time_ms,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        message = json.dumps(payload, default=str)

        dead_clients = set()
        for ws in self._ws_clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead_clients.add(ws)

        for ws in dead_clients:
            self._ws_clients.discard(ws)

    # ── Alert dedup ──────────────────────────────────────────

    def _create_alert(
        self,
        alert_type: AlertType,
        message: str,
        severity: AlertSeverity,
        student_id: Optional[str] = None,
    ) -> Optional[AlertPayload]:
        """Create an alert with cooldown-based deduplication."""
        key = f"{alert_type.value}:{student_id or 'class'}"
        now = time.time()

        if key in self._last_alert:
            if now - self._last_alert[key] < self._alert_cooldown:
                return None  # still in cooldown

        self._last_alert[key] = now
        return AlertPayload(
            type=alert_type,
            message=message,
            severity=severity,
            student_id=student_id,
            session_id=self._session_id,
        )

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _bbox_iou(a: BoundingBox, b: BoundingBox) -> float:
        """Compute intersection-over-union between two normalised bboxes."""
        xa = max(a.x, b.x)
        ya = max(a.y, b.y)
        xb = min(a.x + a.w, b.x + b.w)
        yb = min(a.y + a.h, b.y + b.h)

        inter = max(0, xb - xa) * max(0, yb - ya)
        area_a = a.w * a.h
        area_b = b.w * b.h
        union = area_a + area_b - inter

        return inter / union if union > 0 else 0.0
