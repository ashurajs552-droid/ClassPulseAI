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

    # 1. First check in-memory frame processor
    fp = app_state.get("frame_processor")
    live_records = fp.get_session_attendance(session_id) if fp else []

    db = app_state.get("supabase")
    if not db:
        return {"data": live_records, "count": len(live_records)}

    try:
        resp = (
            db.table("attendance")
            .select("*, students(full_name, student_code, photo_url)")
            .eq("session_id", session_id)
            .order("detected_at", desc=False)
            .execute()
        )
        db_records = resp.data or []
        combined = {r.get("student_id"): r for r in (live_records + db_records)}
        res_list = list(combined.values())
        return {"data": res_list, "count": len(res_list)}
    except Exception as exc:
        logger.warning("Attendance DB query failed, using live records: %s", exc)
        return {"data": live_records, "count": len(live_records)}


@router.get("/summary/{session_id}")
async def get_attendance_summary(session_id: str):
    """Get attendance summary (present/absent/late counts) for a session."""
    from main import app_state

    fp = app_state.get("frame_processor")
    live_records = fp.get_session_attendance(session_id) if fp else []

    db = app_state.get("supabase")
    if not db:
        present = sum(1 for r in live_records if r.get("status") == "present")
        late = sum(1 for r in live_records if r.get("status") == "late")
        absent = sum(1 for r in live_records if r.get("status") == "absent")
        total = max(len(live_records), 1)
        return {
            "session_id": session_id,
            "total_enrolled": total,
            "present": present,
            "late": late,
            "absent": absent,
            "attendance_rate": round(((present + late) / total * 100) if total > 0 else 0, 1),
        }

    try:
        resp = (
            db.table("attendance")
            .select("status")
            .eq("session_id", session_id)
            .execute()
        )
        records = resp.data or live_records

        present = sum(1 for r in records if r["status"] == "present")
        late = sum(1 for r in records if r["status"] == "late")
        absent = sum(1 for r in records if r["status"] == "absent")

        total = 30
        try:
            session_resp = (
                db.table("sessions")
                .select("class_id, total_students")
                .eq("id", session_id)
                .single()
                .execute()
            )
            if session_resp.data and session_resp.data.get("total_students"):
                total = session_resp.data["total_students"]
        except Exception:
            pass

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
        return {
            "session_id": session_id,
            "total_enrolled": len(live_records),
            "present": len(live_records),
            "late": 0,
            "absent": 0,
            "attendance_rate": 100.0,
        }


@router.put("/override")
async def override_attendance(
    session_id: str,
    student_id: str,
    status: str = Query(pattern="^(present|absent|late)$"),
):
    """Manually override a student's attendance status."""
    from main import app_state

    fp = app_state.get("frame_processor")
    if fp:
        fp.record_manual_attendance(student_id, status)

    db = app_state.get("supabase")
    if not db:
        return {"message": "Attendance updated in memory", "data": {"session_id": session_id, "student_id": student_id, "status": status}}

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
        return {"message": "Attendance updated in memory", "data": {"session_id": session_id, "student_id": student_id, "status": status}}
