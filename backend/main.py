"""
ClassPulse AI — FastAPI Backend Entry Point

Initialises all AI services on startup, exposes REST + WebSocket endpoints,
and runs the real-time processing pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from models.schemas import HealthCheck
from utils.logger import setup_logging

# ── Logging ──────────────────────────────────────────────────
setup_logging(level="DEBUG" if settings.debug else "INFO", log_file="logs/classpulse.log")
logger = logging.getLogger(__name__)

# ── Global state (populated on startup) ──────────────────────
app_state: dict[str, Any] = {}
_start_time: float = 0.0


# ── Lifespan ─────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load all AI models and services on startup, clean up on shutdown."""
    global _start_time
    _start_time = time.time()
    logger.info("=" * 60)
    logger.info("  ClassPulse AI — Starting up…")
    logger.info("=" * 60)

    # ── Supabase client ──────────────────────────────────────
    supabase_client = None
    if settings.supabase_url and settings.supabase_service_key:
        try:
            from supabase import create_client

            supabase_client = create_client(
                settings.supabase_url, settings.supabase_service_key
            )
            app_state["supabase"] = supabase_client
            logger.info("✓ Supabase client connected.")
        except Exception as exc:
            logger.error("✗ Supabase connection failed: %s", exc)
    else:
        logger.warning("⚠ Supabase credentials not set — running without DB.")

    # ── Redis service ──────────────────────────────────────────
    from services.redis_service import RedisService

    redis_svc = RedisService()
    await redis_svc.connect()
    app_state["redis"] = redis_svc
    if redis_svc.is_loaded:
        logger.info("✓ Redis service connected.")
    else:
        logger.warning("⚠ Redis not available — running without cache.")

    # ── WebSocket manager ────────────────────────────────────
    from websocket_manager import WebSocketManager

    ws_manager = WebSocketManager()
    ws_manager.start()
    app_state["ws_manager"] = ws_manager
    logger.info("✓ WebSocket manager started.")

    # ── Camera service ───────────────────────────────────────
    from services.camera_service import CameraService

    camera = CameraService()
    app_state["camera"] = camera
    logger.info("✓ Camera service ready (not started until stream/start).")

    # ── Face detection ───────────────────────────────────────
    from services.face_detection import FaceDetectionService

    face_detector = FaceDetectionService()
    face_detector.load()
    app_state["face_detector"] = face_detector
    logger.info("✓ Face detection loaded.")

    # ── Face recognition ─────────────────────────────────────
    from services.face_recognition import FaceRecognitionService

    recogniser = FaceRecognitionService()
    recogniser.load(supabase_client)
    app_state["recogniser"] = recogniser
    logger.info("✓ Face recognition loaded (%d enrolled).", recogniser.enrolled_count)

    # ── Emotion detection ────────────────────────────────────
    from services.emotion_detection import EmotionDetectionService

    emotion_detector = EmotionDetectionService()
    emotion_detector.load()
    app_state["emotion_detector"] = emotion_detector
    logger.info("✓ Emotion detection loaded.")

    # ── Phone detection ──────────────────────────────────────
    from services.phone_detection import PhoneDetectionService

    phone_detector = PhoneDetectionService()
    phone_detector.load()
    app_state["phone_detector"] = phone_detector
    logger.info("✓ Phone detection loaded.")

    # ── Tracking ─────────────────────────────────────────────
    from services.tracking_service import TrackingService

    tracker = TrackingService()
    tracker.load()
    app_state["tracker"] = tracker
    logger.info("✓ DeepSORT tracker loaded.")

    # ── Engagement scorer ────────────────────────────────────
    from services.engagement_scorer import EngagementScorerService

    scorer = EngagementScorerService()
    scorer.load()
    app_state["scorer"] = scorer
    logger.info("✓ Engagement scorer loaded.")

    # ── Analytics service ────────────────────────────────────
    from services.analytics_service import AnalyticsService

    analytics = AnalyticsService(supabase_client)
    analytics.load(supabase_client)
    app_state["analytics"] = analytics
    logger.info("✓ Analytics service loaded.")

    # ── Report generator ─────────────────────────────────────
    from services.report_generator import ReportGeneratorService

    report_gen = ReportGeneratorService(supabase_client)
    report_gen.load(supabase_client)
    app_state["report_generator"] = report_gen
    logger.info("✓ Report generator loaded.")

    # ── Frame processor (pipeline orchestrator) ──────────────
    from utils.frame_processor import FrameProcessor

    processor = FrameProcessor(
        camera=camera,
        face_detector=face_detector,
        tracker=tracker,
        recogniser=recogniser,
        emotion_detector=emotion_detector,
        phone_detector=phone_detector,
        engagement_scorer=scorer,
        supabase_client=supabase_client,
    )
    app_state["processor"] = processor
    logger.info("✓ Frame processor ready.")

    # ── System info ──────────────────────────────────────────
    from utils.gpu_accelerator import system_info

    info = system_info()
    for k, v in info.items():
        logger.info("  %s: %s", k, v)

    logger.info("=" * 60)
    logger.info("  ClassPulse AI — All systems go! 🚀")
    logger.info("=" * 60)

    yield  # ── app is running ──

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("Shutting down…")
    camera.stop()
    face_detector.unload()
    recogniser.unload()
    emotion_detector.unload()
    phone_detector.unload()
    tracker.unload()
    scorer.unload()
    analytics.unload()
    report_gen.unload()

    # Shutdown WebSocket manager
    if ws_manager:
        await ws_manager.shutdown()

    # Disconnect Redis
    if redis_svc:
        await redis_svc.disconnect()

    logger.info("Shutdown complete.")


# ── App ──────────────────────────────────────────────────────

app = FastAPI(
    title="ClassPulse AI",
    description="AI-Powered Classroom Monitoring System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────
from routers.stream import router as stream_router
from routers.attendance import router as attendance_router
from routers.analytics import router as analytics_router
from routers.reports import router as reports_router

app.include_router(stream_router)
app.include_router(attendance_router)
app.include_router(analytics_router)
app.include_router(reports_router)


# ── Health check ─────────────────────────────────────────────

@app.get("/health", response_model=HealthCheck, tags=["system"])
async def health_check():
    """System health and model status."""
    return HealthCheck(
        status="healthy",
        version="1.0.0",
        models_loaded={
            "face_detection": app_state.get("face_detector", None) is not None
            and app_state["face_detector"].is_loaded,
            "face_recognition": app_state.get("recogniser", None) is not None
            and app_state["recogniser"].is_loaded,
            "emotion_detection": app_state.get("emotion_detector", None) is not None
            and app_state["emotion_detector"].is_loaded,
            "phone_detection": app_state.get("phone_detector", None) is not None
            and app_state["phone_detector"].is_loaded,
            "tracking": app_state.get("tracker", None) is not None
            and app_state["tracker"].is_loaded,
        },
        uptime_seconds=round(time.time() - _start_time, 1),
    )


# ── WebSocket: live stream ───────────────────────────────────

@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket, session_id: str | None = None):
    """
    Live stream WebSocket endpoint.

    Uses the WebSocketManager for connection lifecycle, heartbeat,
    per-session room routing, and typed message broadcasting.
    """
    from websocket_manager import WebSocketManager, MessageType

    manager: WebSocketManager = app_state.get("ws_manager")
    if not manager:
        await ws.close(code=1011, reason="Server not ready")
        return

    client_id = await manager.connect(ws, session_id)

    try:
        while True:
            raw = await ws.receive_text()
            result = await manager.handle_client_message(client_id, raw)

            # handle_client_message returns None for internally handled msgs
            # (ping, join_session, leave_session) — otherwise we act on it:
            if result:
                cmd = result.get("command") or result.get("type")

                if cmd == "start_session":
                    sid = result.get("session_id")
                    processor = app_state.get("processor")
                    camera = app_state.get("camera")
                    redis_svc = app_state.get("redis")

                    if sid:
                        await manager.join_session(client_id, sid)
                        if processor:
                            processor.set_session(sid)
                        if camera and not camera.is_running:
                            camera.start()
                        if redis_svc and redis_svc.is_loaded:
                            from datetime import datetime
                            await redis_svc.set_session_state(
                                sid, "active",
                                started_at=datetime.utcnow().isoformat(),
                            )
                        await manager.broadcast_session_update(sid, "active")

                elif cmd == "stop_session":
                    camera = app_state.get("camera")
                    redis_svc = app_state.get("redis")
                    if camera:
                        camera.stop()
                    # Get the client's session before leaving
                    client = manager._clients.get(client_id)
                    sid = client.session_id if client else None
                    if sid:
                        await manager.broadcast_session_update(sid, "completed")
                        if redis_svc and redis_svc.is_loaded:
                            await redis_svc.set_session_state(sid, "completed")

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("WebSocket error for %s: %s", client_id, exc)
    finally:
        await manager.disconnect(client_id)


@app.get("/api/ws/stats", tags=["system"])
async def ws_stats():
    """WebSocket manager statistics."""
    manager = app_state.get("ws_manager")
    return manager.get_stats() if manager else {}


@app.get("/api/redis/health", tags=["system"])
async def redis_health():
    """Redis health info."""
    redis_svc = app_state.get("redis")
    if redis_svc:
        return await redis_svc.health()
    return {"status": "not_configured"}


# ── Students CRUD (inline for simplicity) ────────────────────

@app.get("/api/students", tags=["students"])
async def list_students(class_id: str | None = None, active_only: bool = True):
    """List all students with optional class filter."""
    db = app_state.get("supabase")
    if not db:
        return {"data": [], "error": "No database"}

    try:
        query = db.table("students").select(
            "id, student_code, full_name, class_id, photo_url, enrollment_date, is_active, "
            "classes(name)"
        ).order("full_name")

        if class_id:
            query = query.eq("class_id", class_id)
        if active_only:
            query = query.eq("is_active", True)

        resp = query.execute()
        return {"data": resp.data or []}
    except Exception as exc:
        logger.error("Students query failed: %s", exc)
        return {"data": [], "error": str(exc)}


@app.post("/api/students", tags=["students"])
async def create_student(student: dict):
    """Create a new student record."""
    db = app_state.get("supabase")
    if not db:
        return {"error": "No database"}

    try:
        resp = db.table("students").insert(student).execute()
        return {"data": resp.data}
    except Exception as exc:
        logger.error("Student creation failed: %s", exc)
        return {"error": str(exc)}


@app.put("/api/students/{student_id}", tags=["students"])
async def update_student(student_id: str, updates: dict):
    """Update a student record."""
    db = app_state.get("supabase")
    if not db:
        return {"error": "No database"}

    try:
        resp = db.table("students").update(updates).eq("id", student_id).execute()
        return {"data": resp.data}
    except Exception as exc:
        logger.error("Student update failed: %s", exc)
        return {"error": str(exc)}


@app.delete("/api/students/{student_id}", tags=["students"])
async def delete_student(student_id: str):
    """Soft-delete a student (set is_active=false)."""
    db = app_state.get("supabase")
    if not db:
        return {"error": "No database"}

    try:
        resp = (
            db.table("students")
            .update({"is_active": False})
            .eq("id", student_id)
            .execute()
        )
        # Remove from recognition cache
        recogniser = app_state.get("recogniser")
        if recogniser:
            recogniser.remove(student_id)

        return {"data": resp.data}
    except Exception as exc:
        logger.error("Student deletion failed: %s", exc)
        return {"error": str(exc)}


# ── Classes CRUD ─────────────────────────────────────────────

@app.get("/api/classes", tags=["classes"])
async def list_classes(teacher_id: str | None = None):
    """List all classes."""
    db = app_state.get("supabase")
    if not db:
        return {"data": []}

    try:
        query = db.table("classes").select("*, profiles(full_name)").order("name")
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        resp = query.execute()
        return {"data": resp.data or []}
    except Exception as exc:
        logger.error("Classes query failed: %s", exc)
        return {"data": [], "error": str(exc)}


# ── Run ──────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
        ws_ping_interval=20,
        ws_ping_timeout=30,
        timeout_keep_alive=30,
    )
