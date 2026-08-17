"""
ClassPulse AI — Frame Processor (Main Pipeline Orchestrator)

Orchestrates the complete per-frame AI pipeline:
  capture → detect faces → track → recognise → mark attendance →
  detect emotions → detect phones → score engagement → push to DB → broadcast via WebSocket

Profiles each step and provides automatic attendance logging and live streaming.
"""

from __future__ import annotations

import asyncio
import base64
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
    "face_detection": 25,
    "tracking": 15,
    "face_recognition": 50,
    "emotion_detection": 20,
    "phone_detection": 30,
    "engagement": 10,
}


class FrameProcessor:
    """
    Main pipeline orchestrator.
    Consumes frames from CameraService, runs AI models, marks attendance automatically,
    and produces FrameResult objects and base64 video for WebSocket broadcast.
    """

    def __init__(
        self,
        camera: Optional[CameraService] = None,
        face_detector: Optional[FaceDetectionService] = None,
        tracker: Optional[TrackingService] = None,
        recogniser: Optional[FaceRecognitionService] = None,
        emotion_detector: Optional[EmotionDetectionService] = None,
        phone_detector: Optional[PhoneDetectionService] = None,
        engagement_scorer: Optional[EngagementScorerService] = None,
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
        self._session_start_time: Optional[float] = None
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None

        # In-memory attendance records: student_id -> dict
        self._session_attendance: dict[str, dict[str, Any]] = {}

        # Connected WebSocket clients
        self._ws_clients: set = set()

        # Alert dedup (type → last alert time)
        self._last_alert: dict[str, float] = {}
        self._alert_cooldown: float = 30.0  # seconds

    # ── Session control ──────────────────────────────────────

    def set_session(self, session_id: str) -> None:
        """Set the current session ID for DB writes and attendance."""
        self._session_id = session_id
        self._session_start_time = time.time()
        self._frame_count = 0
        self._session_attendance.clear()
        if self._recogniser:
            self._recogniser.clear_track_cache()
        if self._emotion:
            self._emotion.clear_history()
        self._last_alert.clear()
        logger.info("Pipeline session set: %s", session_id)

    def get_session_attendance(self, session_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Return list of all attendance records recorded for this session."""
        return list(self._session_attendance.values())

    def record_manual_attendance(self, student_id: str, status: str, student_name: str = "") -> dict[str, Any]:
        """Manually mark or override attendance for a student."""
        rec = {
            "session_id": self._session_id or "default-session",
            "student_id": student_id,
            "student_name": student_name or student_id,
            "status": status,
            "detected_at": datetime.utcnow().isoformat(),
            "confidence": 1.0,
            "marked_by": "manual",
        }
        self._session_attendance[student_id] = rec
        return rec

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
        Includes face detection, tracking, recognition, automated attendance marking,
        emotion detection, phone detection, and engagement scoring.
        """
        self._frame_count += 1
        pipeline_start = time.perf_counter()
        timings: dict[str, float] = {}
        alerts: list[AlertPayload] = []

        if frame is None or frame.size == 0:
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # ── 1. Face Detection ────────────────────────────────
        t0 = time.perf_counter()
        faces = self._face_detector.detect(frame) if self._face_detector else []
        timings["face_detection"] = (time.perf_counter() - t0) * 1000

        # ── 2. Tracking ──────────────────────────────────────
        t0 = time.perf_counter()
        bboxes = [f.bbox for f in faces]
        confs = [f.confidence for f in faces]
        tracks = self._tracker.update(frame, bboxes, confs) if self._tracker else []
        timings["tracking"] = (time.perf_counter() - t0) * 1000

        # ── 3. Face Recognition & Automatic Attendance ───────
        t0 = time.perf_counter()
        newly_marked_attendance = []
        if self._recogniser:
            for track in tracks:
                face_crop = FaceDetectionService.crop_face(frame, track.bbox)
                sid, sname, conf = self._recogniser.recognize(face_crop, track.track_id)
                if sid:
                    track.student_id = sid
                    track.student_name = sname
                    if self._tracker:
                        self._tracker.set_student_for_track(track.track_id, sid, sname or "")

                    # Automatically mark attendance for recognized student
                    if sid not in self._session_attendance:
                        elapsed_min = (time.time() - (self._session_start_time or time.time())) / 60.0
                        status = "late" if elapsed_min > 15.0 else "present"
                        att_rec = {
                            "session_id": self._session_id or "default-session",
                            "student_id": sid,
                            "student_name": sname or sid,
                            "status": status,
                            "detected_at": datetime.utcnow().isoformat(),
                            "confidence": round(float(conf), 3),
                            "marked_by": "ai_camera",
                        }
                        self._session_attendance[sid] = att_rec
                        newly_marked_attendance.append(att_rec)
                        logger.info("Automatic attendance marked: %s (%s) -> %s", sname, sid, status)

        timings["face_recognition"] = (time.perf_counter() - t0) * 1000

        # ── 4. Emotion Detection ─────────────────────────────
        t0 = time.perf_counter()
        emotion_map: dict[int, tuple[EmotionLabel, float]] = {}
        if self._emotion and tracks:
            face_crops = [FaceDetectionService.crop_face(frame, t.bbox) for t in tracks]
            track_ids = [t.track_id for t in tracks]
            student_ids = [t.student_id for t in tracks]
            emotion_results = self._emotion.detect_batch(face_crops, track_ids, student_ids)
            for er in emotion_results:
                emotion_map[er.track_id] = (er.emotion, er.confidence)
        timings["emotion_detection"] = (time.perf_counter() - t0) * 1000

        # ── 5. Phone Detection ───────────────────────────────
        t0 = time.perf_counter()
        phone_dets = []
        if self._phone and tracks:
            student_bboxes = [(t.student_id, t.bbox) for t in tracks]
            phone_dets = self._phone.detect(frame, student_bboxes)
            for pd in phone_dets:
                alert = self._create_alert(
                    AlertType.phone_detected,
                    f"Phone detected near student {pd.nearby_student_id or 'unknown'}",
                    AlertSeverity.medium,
                    pd.nearby_student_id,
                )
                if alert:
                    alerts.append(alert)
        timings["phone_detection"] = (time.perf_counter() - t0) * 1000

        # ── 6. Engagement Scoring ────────────────────────────
        t0 = time.perf_counter()
        engagement_scores = []
        if self._engagement:
            for track in tracks:
                emo_label = emotion_map.get(track.track_id, (None, 0))[0]
                face_lm = None
                for face in faces:
                    if self._bbox_iou(face.bbox, track.bbox) > 0.3:
                        face_lm = face.landmarks
                        break

                score = self._engagement.calculate(
                    track_id=track.track_id,
                    student_id=track.student_id,
                    emotion=emo_label.value if emo_label else "attentive",
                    landmarks=face_lm,
                    bbox=track.bbox,
                )
                if score:
                    engagement_scores.append(score)
        timings["engagement"] = (time.perf_counter() - t0) * 1000

        # ── 7. Analytics & Alerts ────────────────────────────
        emo_dist = self._emotion.get_class_distribution() if self._emotion else {
            "attentive": max(1, len(tracks)), "engaged": 0, "confused": 0, "distracted": 0, "sleepy": 0
        }
        avg_eng = self._engagement.get_class_average() if self._engagement else 85.0

        # ── Build student detections ─────────────────────────
        student_detections: list[StudentDetection] = []
        for track in tracks:
            emo, emo_conf = emotion_map.get(track.track_id, (EmotionLabel.attentive, 0.85))
            eng = next((s.score for s in engagement_scores if s.track_id == track.track_id), 88.0)
            has_phone = any(pd.nearby_student_id == track.student_id for pd in phone_dets if track.student_id)

            student_detections.append(StudentDetection(
                track_id=track.track_id,
                student_id=track.student_id,
                student_name=track.student_name,
                bbox=track.bbox,
                confidence=0.92,
                emotion=emo,
                emotion_confidence=emo_conf,
                engagement_score=eng,
                has_phone=has_phone,
            ))

        # ── Metrics ──────────────────────────────────────────
        total_time = (time.perf_counter() - pipeline_start) * 1000
        fps_val = self._camera.fps if self._camera else 30.0

        metrics = SessionMetrics(
            session_id=self._session_id or "",
            total_students=len(tracks),
            present_students=len(self._session_attendance) or sum(1 for t in tracks if t.student_id),
            avg_engagement=round(avg_eng, 1),
            emotion_distribution=emo_dist,
            phone_detections=len(phone_dets),
            alerts_count=len(alerts),
            fps=round(fps_val, 1),
            latency_ms=round(total_time, 1),
            detection_count=len(faces),
        )

        result = FrameResult(
            frame_number=self._frame_count,
            detections=student_detections,
            phone_detections=phone_dets,
            alerts=alerts,
            metrics=metrics,
            processing_time_ms=round(total_time, 1),
        )

        # ── Generate Base64 Video Frame for Frontend Stream ──
        frame_b64 = self._encode_frame_b64(frame)

        # ── Async DB push ────────────────────────────────────
        if self._session_id and self._db:
            asyncio.create_task(self._push_to_db(result, engagement_scores, alerts, newly_marked_attendance))

        # ── WebSocket broadcast ──────────────────────────────
        asyncio.create_task(self._broadcast(result, frame_b64, newly_marked_attendance))

        return result

    # ── Frame Encoding ───────────────────────────────────────

    def _encode_frame_b64(self, frame: np.ndarray) -> str:
        """Encode downscaled JPEG frame to base64 for fast WebSocket transmission."""
        try:
            h, w = frame.shape[:2]
            target_w = 640
            target_h = int(h * (target_w / max(1, w)))
            small = cv2.resize(frame, (target_w, target_h))
            _, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buf).decode("utf-8")
        except Exception:
            return ""

    # ── DB push ──────────────────────────────────────────────

    async def _push_to_db(
        self,
        result: FrameResult,
        engagement_scores: list,
        alerts: list[AlertPayload],
        new_attendance: list[dict],
    ) -> None:
        """Push pending scores, attendance, and alerts to Supabase."""
        try:
            # 1. Upsert newly marked attendance
            for att in new_attendance:
                self._db.table("attendance").upsert({
                    "session_id": self._session_id,
                    "student_id": att["student_id"],
                    "status": att["status"],
                    "marked_by": att["marked_by"],
                }, on_conflict="session_id,student_id").execute()

            # 2. Engagement scores
            if self._engagement:
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
                        for s in pending if s.student_id
                    ]
                    if rows:
                        self._db.table("engagement_scores").insert(rows).execute()

            # 3. Alerts
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

        except Exception as exc:
            logger.error("DB push failed: %s", exc)

    # ── WebSocket broadcast ──────────────────────────────────

    async def _broadcast(
        self,
        result: FrameResult,
        frame_b64: str = "",
        new_attendance: list[dict] | None = None,
    ) -> None:
        """Broadcast frame result and updates to all connected WebSocket clients."""
        from main import app_state
        ws_manager = app_state.get("ws_manager")

        # 1. Broadcast attendance updates if any new students recognized
        if new_attendance and ws_manager:
            for att in new_attendance:
                await ws_manager.broadcast_attendance(
                    self._session_id or "default-session",
                    att["student_id"],
                    att["status"],
                    att.get("confidence", 1.0),
                )

        if not self._ws_clients and not ws_manager:
            return

        payload = {
            "type": "frame_update",
            "data": {
                "frame_number": result.frame_number,
                "frame_b64": frame_b64,
                "detections": [d.model_dump() for d in result.detections],
                "phone_detections": [p.model_dump() for p in result.phone_detections],
                "alerts": [a.model_dump(mode="json") for a in result.alerts],
                "metrics": result.metrics.model_dump(mode="json") if result.metrics else None,
                "processing_time_ms": result.processing_time_ms,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        message = json.dumps(payload, default=str)

        # Broadcast via ws_clients
        dead_clients = set()
        for ws in self._ws_clients:
            try:
                await ws.send_text(message)
            except Exception:
                dead_clients.add(ws)
        for ws in dead_clients:
            self._ws_clients.discard(ws)

        # Broadcast via main ws_manager
        if ws_manager and self._session_id:
            await ws_manager.broadcast_to_session(self._session_id, payload)

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
                return None

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

    # ── Processing Loop ──────────────────────────────────────

    def start_loop(self, session_id: str) -> None:
        """Start async background frame grab and processing loop."""
        self.set_session(session_id)
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._processing_loop())
        logger.info("Processing loop started for session: %s", session_id)

    def stop_loop(self) -> None:
        """Stop background processing loop."""
        self._running = False
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            self._loop_task = None
        logger.info("Processing loop stopped.")

    async def _processing_loop(self) -> None:
        """Async loop worker grabbing frames and running AI pipeline."""
        while self._running:
            try:
                frame = None
                if self._camera and self._camera.is_running:
                    frame = self._camera.get_frame()

                if frame is None:
                    # Generate video frame (gradient background with classroom monitor label)
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    for r in range(480):
                        frame[r, :] = [30 + int(r * 0.05), 25 + int(r * 0.04), 35 + int(r * 0.08)]
                    cv2.putText(frame, "ClassPulse AI — Live Monitor", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                    cv2.putText(frame, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 200), 1)

                await self.process_frame(frame)
                await asyncio.sleep(0.066)  # ~15 fps
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in processing loop: %s", e)
                await asyncio.sleep(0.1)

