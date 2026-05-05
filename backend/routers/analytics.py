"""
ClassPulse AI — Analytics Router

Endpoints for session-level analytics, trends, and comparison data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/session/{session_id}")
async def get_session_analytics(session_id: str):
    """Get complete analytics for a single session."""
    from main import app_state

    analytics = app_state.get("analytics")
    if not analytics:
        raise HTTPException(500, "Analytics service not available")

    return analytics.get_session_metrics(session_id)


@router.get("/session/{session_id}/engagement-trend")
async def get_engagement_trend(session_id: str):
    """Get time-bucketed engagement data for charting."""
    from main import app_state

    analytics = app_state.get("analytics")
    if not analytics:
        raise HTTPException(500, "Analytics service not available")

    return analytics.get_engagement_trend(session_id)


@router.get("/session/{session_id}/per-student")
async def get_per_student_engagement(session_id: str):
    """Get per-student engagement breakdown."""
    from main import app_state

    analytics = app_state.get("analytics")
    if not analytics:
        raise HTTPException(500, "Analytics service not available")

    return analytics.get_per_student_engagement(session_id)


@router.get("/sessions")
async def list_sessions(
    teacher_id: str | None = None,
    class_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List sessions with optional filters."""
    from main import app_state

    db = app_state.get("supabase")
    if not db:
        raise HTTPException(500, "Database not available")

    try:
        query = (
            db.table("sessions")
            .select("*, classes(name, room_number)")
            .order("started_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        if class_id:
            query = query.eq("class_id", class_id)
        if status:
            query = query.eq("status", status)

        resp = query.execute()
        return {"data": resp.data or [], "count": len(resp.data or [])}
    except Exception as exc:
        logger.error("Sessions query failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.get("/emotion-timeline/{session_id}")
async def get_emotion_timeline(session_id: str):
    """Get emotion logs over time for heatmap/timeline charts."""
    from main import app_state

    db = app_state.get("supabase")
    if not db:
        raise HTTPException(500, "Database not available")

    try:
        resp = (
            db.table("emotion_logs")
            .select("emotion, confidence, timestamp, student_id")
            .eq("session_id", session_id)
            .order("timestamp", desc=False)
            .execute()
        )
        return {"data": resp.data or []}
    except Exception as exc:
        logger.error("Emotion timeline query failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.get("/alerts/{session_id}")
async def get_session_alerts(session_id: str):
    """Get all alerts for a session."""
    from main import app_state

    db = app_state.get("supabase")
    if not db:
        raise HTTPException(500, "Database not available")

    try:
        resp = (
            db.table("alerts")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .execute()
        )
        return {"data": resp.data or []}
    except Exception as exc:
        logger.error("Alerts query failed: %s", exc)
        raise HTTPException(500, str(exc))
