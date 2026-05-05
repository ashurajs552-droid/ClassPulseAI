"""
ClassPulse AI — FastAPI Backend Entry Point

Health check and root endpoints load immediately.
All AI models are lazy-loaded on startup with try/except
so the app starts even if individual models fail.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ── App (defined FIRST so /health works immediately) ─────────

app = FastAPI(
    title="ClassPulse AI",
    description="AI-Powered Classroom Monitoring System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global state ─────────────────────────────────────────────

app_state: dict[str, Any] = {}
_start_time: float = time.time()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Health check + root (always available) ───────────────────

@app.get("/health")
async def health_check():
    """Health check — returns immediately, no model dependency."""
    models_status = {}
    for name in ["face_detector", "recogniser", "emotion_detector", "phone_detector", "tracker"]:
        svc = app_state.get(name)
        models_status[name] = svc is not None and getattr(svc, "is_loaded", False)

    return {
        "status": "healthy",
        "service": "ClassPulse AI",
        "version": "1.0.0",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "models_loaded": models_status,
    }


@app.get("/")
async def root():
    return {"message": "ClassPulse AI Backend Running"}


# ── Lazy startup — all heavy imports inside try/except ───────

@app.on_event("startup")
async def startup_event():
    """Load all AI services lazily. Each wrapped in try/except."""
    logger.info("=" * 60)
    logger.info("  ClassPulse AI — Starting up…")
    logger.info("=" * 60)

    # ── Logging setup ────────────────────────────────────────
    try:
        from utils.logger import setup_logging
        setup_logging(level="INFO", log_file="logs/classpulse.log")
    except Exception as e:
        logger.warning("Logger setup skipped: %s", e)

    # ── Config ───────────────────────────────────────────────
    try:
        from config import settings
        app_state["settings"] = settings
        logger.info("✓ Config loaded.")
    except Exception as e:
        logger.warning("Config load failed: %s", e)

    # ── Supabase client ──────────────────────────────────────
    supabase_client = None
    try:
        from config import settings
        if settings.supabase_url and settings.supabase_service_key:
            from supabase import create_client
            supabase_client = create_client(
                settings.supabase_url, settings.supabase_service_key
            )
            app_state["supabase"] = supabase_client
            logger.info("✓ Supabase client connected.")
        else:
            logger.warning("⚠ Supabase credentials not set — running without DB.")
    except Exception as e:
        logger.warning("⚠ Supabase connection failed: %s", e)

    # ── Redis service ────────────────────────────────────────
    try:
        from services.redis_service import RedisService
        redis_svc = RedisService()
        await redis_svc.connect()
        app_state["redis"] = redis_svc
        if redis_svc.is_loaded:
            logger.info("✓ Redis service connected.")
        else:
            logger.warning("⚠ Redis not available — running without cache.")
    except Exception as e:
        logger.warning("⚠ Redis setup failed: %s", e)

    # ── WebSocket manager ────────────────────────────────────
    try:
        from websocket_manager import WebSocketManager
        ws_manager = WebSocketManager()
        ws_manager.start()
        app_state["ws_manager"] = ws_manager
        logger.info("✓ WebSocket manager started.")
    except Exception as e:
        logger.warning("⚠ WebSocket manager failed: %s", e)

    # ── Camera service ───────────────────────────────────────
    try:
        from services.camera_service import CameraService
        camera = CameraService()
        app_state["camera"] = camera
        logger.info("✓ Camera service ready.")
    except Exception as e:
        logger.warning("⚠ Camera service failed: %s", e)

    # ── Face detection ───────────────────────────────────────
    try:
        from services.face_detection import FaceDetectionService
        face_detector = FaceDetectionService()
        face_detector.load()
        app_state["face_detector"] = face_detector
        logger.info("✓ Face detection loaded.")
    except Exception as e:
        logger.warning("⚠ Face detection failed: %s", e)

    # ── Face recognition ─────────────────────────────────────
    try:
        from services.face_recognition import FaceRecognitionService
        recogniser = FaceRecognitionService()
        recogniser.load(supabase_client)
        app_state["recogniser"] = recogniser
        logger.info("✓ Face recognition loaded (%d enrolled).", recogniser.enrolled_count)
    except Exception as e:
        logger.warning("⚠ Face recognition failed: %s", e)

    # ── Emotion detection ────────────────────────────────────
    try:
        from services.emotion_detection import EmotionDetectionService
        emotion_detector = EmotionDetectionService()
        emotion_detector.load()
        app_state["emotion_detector"] = emotion_detector
        logger.info("✓ Emotion detection loaded.")
    except Exception as e:
        logger.warning("⚠ Emotion detection failed: %s", e)

    # ── Phone detection ──────────────────────────────────────
    try:
        from services.phone_detection import PhoneDetectionService
        phone_detector = PhoneDetectionService()
        phone_detector.load()
        app_state["phone_detector"] = phone_detector
        logger.info("✓ Phone detection loaded.")
    except Exception as e:
        logger.warning("⚠ Phone detection failed: %s", e)

    # ── Tracking ─────────────────────────────────────────────
    try:
        from services.tracking_service import TrackingService
        tracker = TrackingService()
        tracker.load()
        app_state["tracker"] = tracker
        logger.info("✓ DeepSORT tracker loaded.")
    except Exception as e:
        logger.warning("⚠ Tracker failed: %s", e)

    # ── Engagement scorer ────────────────────────────────────
    try:
        from services.engagement_scorer import EngagementScorerService
        scorer = EngagementScorerService()
        scorer.load()
        app_state["scorer"] = scorer
        logger.info("✓ Engagement scorer loaded.")
    except Exception as e:
        logger.warning("⚠ Engagement scorer failed: %s", e)

    # ── Analytics service ────────────────────────────────────
    try:
        from services.analytics_service import AnalyticsService
        analytics = AnalyticsService(supabase_client)
        analytics.load(supabase_client)
        app_state["analytics"] = analytics
        logger.info("✓ Analytics service loaded.")
    except Exception as e:
        logger.warning("⚠ Analytics service failed: %s", e)

    # ── Report generator ─────────────────────────────────────
    try:
        from services.report_generator import ReportGeneratorService
        report_gen = ReportGeneratorService(supabase_client)
        report_gen.load(supabase_client)
        app_state["report_generator"] = report_gen
        logger.info("✓ Report generator loaded.")
    except Exception as e:
        logger.warning("⚠ Report generator failed: %s", e)

    # ── Frame processor ──────────────────────────────────────
    try:
        from utils.frame_processor import FrameProcessor
        processor = FrameProcessor(
            camera=app_state.get("camera"),
            face_detector=app_state.get("face_detector"),
            tracker=app_state.get("tracker"),
            recogniser=app_state.get("recogniser"),
            emotion_detector=app_state.get("emotion_detector"),
            phone_detector=app_state.get("phone_detector"),
            engagement_scorer=app_state.get("scorer"),
            supabase_client=supabase_client,
        )
        app_state["processor"] = processor
        logger.info("✓ Frame processor ready.")
    except Exception as e:
        logger.warning("⚠ Frame processor failed: %s", e)

    # ── System info ──────────────────────────────────────────
    try:
        from utils.gpu_accelerator import system_info
        info = system_info()
        for k, v in info.items():
            logger.info("  %s: %s", k, v)
    except Exception as e:
        logger.warning("System info unavailable: %s", e)

    logger.info("=" * 60)
    logger.info("  ClassPulse AI — Startup complete! 🚀")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Graceful shutdown — release all resources."""
    logger.info("Shutting down…")

    for name in ["camera", "face_detector", "recogniser", "emotion_detector",
                  "phone_detector", "tracker", "scorer", "analytics", "report_generator"]:
        svc = app_state.get(name)
        if svc and hasattr(svc, "stop"):
            try:
                svc.stop()
            except Exception:
                pass
        if svc and hasattr(svc, "unload"):
            try:
                svc.unload()
            except Exception:
                pass

    ws_manager = app_state.get("ws_manager")
    if ws_manager and hasattr(ws_manager, "shutdown"):
        try:
            await ws_manager.shutdown()
        except Exception:
            pass

    redis_svc = app_state.get("redis")
    if redis_svc and hasattr(redis_svc, "disconnect"):
        try:
            await redis_svc.disconnect()
        except Exception:
            pass

    logger.info("Shutdown complete.")


# ── Routers (lazy import) ────────────────────────────────────

try:
    from routers.stream import router as stream_router
    from routers.attendance import router as attendance_router
    from routers.analytics import router as analytics_router
    from routers.reports import router as reports_router

    app.include_router(stream_router)
    app.include_router(attendance_router)
    app.include_router(analytics_router)
    app.include_router(reports_router)
except Exception as e:
    logger.warning("Some routers failed to load: %s", e)


# ── WebSocket: live stream ───────────────────────────────────

@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket, session_id: str | None = None):
    """Live stream WebSocket endpoint."""
    try:
        from websocket_manager import WebSocketManager, MessageType
    except ImportError:
        await ws.close(code=1011, reason="WebSocket manager not available")
        return

    manager = app_state.get("ws_manager")
    if not manager:
        await ws.close(code=1011, reason="Server not ready")
        return

    client_id = await manager.connect(ws, session_id)

    try:
        while True:
            raw = await ws.receive_text()
            result = await manager.handle_client_message(client_id, raw)

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
                        if redis_svc and getattr(redis_svc, "is_loaded", False):
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
                    client = manager._clients.get(client_id)
                    sid = client.session_id if client else None
                    if sid:
                        await manager.broadcast_session_update(sid, "completed")
                        if redis_svc and getattr(redis_svc, "is_loaded", False):
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


# ── Students CRUD ────────────────────────────────────────────

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
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        ws_ping_interval=20,
        ws_ping_timeout=30,
        timeout_keep_alive=30,
    )
