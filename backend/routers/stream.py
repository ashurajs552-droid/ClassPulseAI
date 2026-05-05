"""
ClassPulse AI — Stream Router

REST & WebSocket endpoints for the live video stream.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["stream"])


@router.get("/status")
async def stream_status():
    """Return the current stream processing status."""
    from main import app_state

    camera = app_state.get("camera")
    processor = app_state.get("processor")

    return {
        "camera_running": camera.is_running if camera else False,
        "fps": camera.fps if camera else 0,
        "frame_count": camera.frame_count if camera else 0,
        "session_id": processor._session_id if processor else None,
        "ws_clients": len(processor._ws_clients) if processor else 0,
    }


@router.post("/start")
async def start_stream(session_id: str | None = None):
    """Start the camera capture and processing pipeline."""
    from main import app_state

    camera = app_state.get("camera")
    processor = app_state.get("processor")

    if not camera:
        return {"error": "Camera service not initialised"}

    if camera.is_running:
        return {"message": "Stream already running", "session_id": session_id}

    success = camera.start()
    if not success:
        return {"error": "Failed to start camera"}

    if session_id and processor:
        processor.set_session(session_id)

    return {"message": "Stream started", "session_id": session_id}


@router.post("/stop")
async def stop_stream():
    """Stop the camera capture."""
    from main import app_state

    camera = app_state.get("camera")
    if camera:
        camera.stop()

    return {"message": "Stream stopped"}
