"""
ClassPulse AI — Reports Router

Endpoints to generate and retrieve AI-powered session reports.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from models.schemas import ReportRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate")
async def generate_report(req: ReportRequest):
    """Generate an AI report for a completed session."""
    from main import app_state

    analytics = app_state.get("analytics")
    report_gen = app_state.get("report_generator")

    if not analytics or not report_gen:
        raise HTTPException(500, "Services not available")

    # Gather session metrics
    metrics = analytics.get_session_metrics(req.session_id)
    per_student = analytics.get_per_student_engagement(req.session_id)

    # Generate report
    report = await report_gen.generate(
        session_id=req.session_id,
        teacher_id=req.teacher_id,
        metrics=metrics,
        per_student=per_student,
    )

    return report


@router.get("/session/{session_id}")
async def get_session_reports(session_id: str):
    """Get all reports for a session."""
    from main import app_state

    db = app_state.get("supabase")
    if not db:
        raise HTTPException(500, "Database not available")

    try:
        resp = (
            db.table("reports")
            .select("*")
            .eq("session_id", session_id)
            .order("generated_at", desc=True)
            .execute()
        )
        return {"data": resp.data or []}
    except Exception as exc:
        logger.error("Reports query failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.get("/{report_id}")
async def get_report(report_id: str):
    """Get a single report by ID."""
    from main import app_state

    db = app_state.get("supabase")
    if not db:
        raise HTTPException(500, "Database not available")

    try:
        resp = (
            db.table("reports")
            .select("*")
            .eq("id", report_id)
            .single()
            .execute()
        )
        if not resp.data:
            raise HTTPException(404, "Report not found")
        return resp.data
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Report query failed: %s", exc)
        raise HTTPException(500, str(exc))


@router.get("/")
async def list_reports(teacher_id: str | None = None, limit: int = 20):
    """List all reports, optionally filtered by teacher."""
    from main import app_state

    db = app_state.get("supabase")
    if not db:
        raise HTTPException(500, "Database not available")

    try:
        query = (
            db.table("reports")
            .select("id, session_id, title, summary, generated_at, pdf_url")
            .order("generated_at", desc=True)
            .limit(limit)
        )
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)

        resp = query.execute()
        return {"data": resp.data or []}
    except Exception as exc:
        logger.error("Reports list failed: %s", exc)
        raise HTTPException(500, str(exc))
