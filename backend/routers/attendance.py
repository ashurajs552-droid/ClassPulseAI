"""
ClassPulse AI — Attendance Router

CRUD endpoints for attendance records and session-level summaries.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.get("/session/{session_id}")
async def get_session_attendance(session_id: str):
    """Get all attendance records for a session."""
    from main import app_state

    db = app_state.get("supabase")
    if not db:
        raise HTTPException(500, "Database not available")

    try:
        resp = (
            db.table("attendance")
            .select("*, students(full_name, student_code, photo_url)")
            .eq("session_id", session_id)
            .order("detected_at", desc=False)
            .execute()
        )
        return {"data": resp.data or [], "count": len(resp.data or [])}
    except Exception as exc:
        logger.error("Attendance query failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.get("/summary/{session_id}")
async def get_attendance_summary(session_id: str):
    """Get attendance summary (present/absent/late counts) for a session."""
    from main import app_state

    db = app_state.get("supabase")
    if not db:
        raise HTTPException(500, "Database not available")

    try:
        resp = (
            db.table("attendance")
            .select("status")
            .eq("session_id", session_id)
            .execute()
        )
        records = resp.data or []

        present = sum(1 for r in records if r["status"] == "present")
        late = sum(1 for r in records if r["status"] == "late")
        absent = sum(1 for r in records if r["status"] == "absent")

        # Get total class enrollment
        session_resp = (
            db.table("sessions")
            .select("class_id, total_students")
            .eq("id", session_id)
            .single()
            .execute()
        )
        total = session_resp.data.get("total_students", 0) if session_resp.data else 0

        return {
            "session_id": session_id,
            "total_enrolled": total,
            "present": present,
            "late": late,
            "absent": max(0, total - present - late),
            "attendance_rate": round(
                ((present + late) / total * 100) if total > 0 else 0, 1
            ),
        }
    except Exception as exc:
        logger.error("Attendance summary failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.put("/override")
async def override_attendance(
    session_id: str,
    student_id: str,
    status: str = Query(pattern="^(present|absent|late)$"),
):
    """Manually override a student's attendance status."""
    from main import app_state

    db = app_state.get("supabase")
    if not db:
        raise HTTPException(500, "Database not available")

    try:
        resp = (
            db.table("attendance")
            .upsert({
                "session_id": session_id,
                "student_id": student_id,
                "status": status,
                "marked_by": "manual",
            }, on_conflict="session_id,student_id")
            .execute()
        )
        return {"message": "Attendance updated", "data": resp.data}
    except Exception as exc:
        logger.error("Attendance override failed: %s", exc)
        raise HTTPException(500, str(exc))
