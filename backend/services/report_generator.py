"""
ClassPulse AI — AI Report Generator

Uses Anthropic Claude to generate structured classroom session reports.
Produces JSON insights and a branded PDF, then uploads to Supabase Storage.
"""

from __future__ import annotations

import io
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from config import settings

logger = logging.getLogger(__name__)


class ReportGeneratorService:
    """Claude-powered report generator with PDF export."""

    def __init__(self, supabase_client=None) -> None:
        self._db = supabase_client
        self._anthropic_client = None
        self._loaded = False

    # ── Lifecycle ────────────────────────────────────────────

    def load(self, supabase_client=None) -> None:
        """Initialise the Anthropic client."""
        if supabase_client:
            self._db = supabase_client

        if settings.anthropic_api_key:
            try:
                import anthropic

                self._anthropic_client = anthropic.Anthropic(
                    api_key=settings.anthropic_api_key
                )
                logger.info("Anthropic client initialised (model=%s).", settings.report_model)
            except Exception as exc:
                logger.warning("Anthropic client init failed: %s", exc)
        else:
            logger.warning("ANTHROPIC_API_KEY not set — reports will use fallback.")

        self._loaded = True

    def unload(self) -> None:
        self._anthropic_client = None
        self._db = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Generation ───────────────────────────────────────────

    async def generate(
        self,
        session_id: str,
        teacher_id: str,
        metrics: dict[str, Any],
        per_student: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a complete AI report for a session.

        Steps:
            1. Build a prompt with session analytics
            2. Call Claude for structured JSON insights
            3. Generate a branded PDF
            4. Upload PDF to Supabase Storage
            5. Insert report record into the reports table

        Returns:
            The full report dict (id, title, summary, insights, ...)
        """
        report_id = str(uuid.uuid4())

        # Step 1: AI generation
        ai_response = await self._call_claude(metrics, per_student or [])

        title = ai_response.get("title", f"Session Report — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}")
        summary = ai_response.get("summary", "Report generation completed.")
        insights = ai_response.get("key_insights", [])
        student_highlights = ai_response.get("student_highlights", [])
        recommendations = ai_response.get("recommendations", [])

        # Step 2: PDF
        pdf_bytes = self._generate_pdf(
            title=title,
            summary=summary,
            insights=insights,
            student_highlights=student_highlights,
            recommendations=recommendations,
            metrics=metrics,
        )

        # Step 3: Upload to Supabase Storage
        pdf_url = None
        if self._db and pdf_bytes:
            pdf_url = self._upload_pdf(report_id, pdf_bytes)

        # Step 4: Persist to DB
        report_record = {
            "id": report_id,
            "session_id": session_id,
            "teacher_id": teacher_id,
            "title": title,
            "summary": summary,
            "insights": insights,
            "recommendations": recommendations,
            "metrics_snapshot": metrics,
            "generated_at": datetime.utcnow().isoformat(),
            "pdf_url": pdf_url,
        }

        if self._db:
            try:
                self._db.table("reports").insert(report_record).execute()
                logger.info("Report %s saved to database.", report_id)
            except Exception as exc:
                logger.error("Failed to save report to DB: %s", exc)

        return report_record

    # ── Claude API call ──────────────────────────────────────

    async def _call_claude(
        self,
        metrics: dict[str, Any],
        per_student: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Call Claude to produce structured report JSON."""

        prompt = self._build_prompt(metrics, per_student)

        if not self._anthropic_client:
            logger.warning("No Anthropic client — returning fallback report.")
            return self._fallback_report(metrics)

        try:
            message = self._anthropic_client.messages.create(
                model=settings.report_model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                system=(
                    "You are ClassPulse AI, an expert educational analyst. "
                    "Generate structured JSON classroom reports. "
                    "Be specific, data-driven, and actionable. "
                    "Always respond with valid JSON only, no markdown fences."
                ),
            )

            raw = message.content[0].text.strip()
            # Strip potential markdown code fences
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]

            return json.loads(raw)

        except json.JSONDecodeError:
            logger.error("Claude returned invalid JSON.")
            return self._fallback_report(metrics)
        except Exception as exc:
            logger.exception("Claude API call failed: %s", exc)
            return self._fallback_report(metrics)

    def _build_prompt(
        self,
        metrics: dict[str, Any],
        per_student: list[dict[str, Any]],
    ) -> str:
        """Build the analysis prompt with session data."""
        student_section = ""
        if per_student:
            student_lines = "\n".join(
                f"  - {s.get('student_name', 'Unknown')}: "
                f"engagement={s.get('avg_engagement', 0):.0f}%, "
                f"emotion={s.get('dominant_emotion', 'N/A')}, "
                f"attendance={s.get('attendance_status', 'N/A')}"
                for s in per_student[:20]
            )
            student_section = f"\n\nPer-Student Data:\n{student_lines}"

        return f"""Analyse this classroom session and generate a structured report.

Session Metrics:
- Attendance Rate: {metrics.get('attendance_rate', 0)}%
- Total Students: {metrics.get('total_students', 0)}
- Present: {metrics.get('present_count', 0)}
- Average Engagement: {metrics.get('avg_engagement', 0)}%
- Emotion Distribution: {json.dumps(metrics.get('emotion_distribution', {}))}
- Phone Detections: {metrics.get('phone_detections', 0)}
- Alerts: {metrics.get('alerts_count', 0)} (Unresolved: {metrics.get('alerts_unresolved', 0)})
- Duration: {metrics.get('duration_minutes', 0)} minutes{student_section}

Respond with a JSON object containing:
{{
  "title": "Brief report title",
  "summary": "2-3 paragraph executive summary of the session",
  "key_insights": [
    {{"title": "...", "description": "...", "metric": "...", "icon": "chart|alert|star|target"}}
  ],
  "student_highlights": [
    {{"student_name": "...", "notes": "1-2 sentence observation"}}
  ],
  "recommendations": ["actionable recommendation 1", "..."]
}}

Provide 4-6 key insights and 3-5 recommendations. Be specific and data-driven."""

    @staticmethod
    def _fallback_report(metrics: dict[str, Any]) -> dict[str, Any]:
        """Generate a basic report when Claude is unavailable."""
        att = metrics.get("attendance_rate", 0)
        eng = metrics.get("avg_engagement", 0)
        total = metrics.get("total_students", 0)

        return {
            "title": f"Session Report — {datetime.utcnow().strftime('%B %d, %Y')}",
            "summary": (
                f"This session had {total} enrolled students with a "
                f"{att:.0f}% attendance rate. Average engagement was "
                f"{eng:.0f}%. "
                f"There were {metrics.get('phone_detections', 0)} phone "
                f"detections and {metrics.get('alerts_count', 0)} alerts raised."
            ),
            "key_insights": [
                {
                    "title": "Attendance",
                    "description": f"{att:.0f}% of students were present.",
                    "metric": f"{att:.0f}%",
                    "icon": "chart",
                },
                {
                    "title": "Engagement",
                    "description": f"Average engagement score was {eng:.0f}%.",
                    "metric": f"{eng:.0f}%",
                    "icon": "target",
                },
            ],
            "student_highlights": [],
            "recommendations": [
                "Review session recording to identify low-engagement periods.",
                "Consider interactive activities to boost participation.",
                "Address phone usage through classroom policy reminders.",
            ],
        }

    # ── PDF generation ───────────────────────────────────────

    def _generate_pdf(
        self,
        title: str,
        summary: str,
        insights: list[dict],
        student_highlights: list[dict],
        recommendations: list[str],
        metrics: dict[str, Any],
    ) -> Optional[bytes]:
        """Generate a branded PDF report using ReportLab."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=20 * mm,
                rightMargin=20 * mm,
                topMargin=25 * mm,
                bottomMargin=20 * mm,
            )

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                "ReportTitle",
                parent=styles["Title"],
                fontSize=22,
                textColor=colors.HexColor("#6366f1"),
                spaceAfter=6 * mm,
            )
            heading_style = ParagraphStyle(
                "ReportHeading",
                parent=styles["Heading2"],
                fontSize=14,
                textColor=colors.HexColor("#8b5cf6"),
                spaceBefore=8 * mm,
                spaceAfter=3 * mm,
            )
            body_style = ParagraphStyle(
                "ReportBody",
                parent=styles["Normal"],
                fontSize=10,
                leading=14,
                spaceAfter=2 * mm,
            )

            story: list = []

            # Header
            story.append(Paragraph("ClassPulse AI", ParagraphStyle(
                "Brand", parent=styles["Normal"],
                fontSize=10, textColor=colors.HexColor("#64748b"),
            )))
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(title, title_style))
            story.append(Paragraph(
                f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                ParagraphStyle("Date", parent=styles["Normal"],
                               fontSize=9, textColor=colors.gray),
            ))
            story.append(Spacer(1, 6 * mm))

            # Summary
            story.append(Paragraph("Executive Summary", heading_style))
            story.append(Paragraph(summary, body_style))

            # Key Metrics table
            story.append(Paragraph("Key Metrics", heading_style))
            metric_data = [
                ["Metric", "Value"],
                ["Attendance Rate", f"{metrics.get('attendance_rate', 0):.1f}%"],
                ["Average Engagement", f"{metrics.get('avg_engagement', 0):.1f}%"],
                ["Total Students", str(metrics.get("total_students", 0))],
                ["Phone Detections", str(metrics.get("phone_detections", 0))],
                ["Alerts", str(metrics.get("alerts_count", 0))],
                ["Duration", f"{metrics.get('duration_minutes', 0):.0f} min"],
            ]
            t = Table(metric_data, colWidths=[80 * mm, 60 * mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6366f1")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)

            # Insights
            if insights:
                story.append(Paragraph("Key Insights", heading_style))
                for ins in insights:
                    story.append(Paragraph(
                        f"<b>{ins.get('title', '')}</b>: {ins.get('description', '')}",
                        body_style,
                    ))

            # Recommendations
            if recommendations:
                story.append(Paragraph("Recommendations", heading_style))
                for i, rec in enumerate(recommendations, 1):
                    story.append(Paragraph(f"{i}. {rec}", body_style))

            doc.build(story)
            return buffer.getvalue()

        except Exception as exc:
            logger.exception("PDF generation failed: %s", exc)
            return None

    # ── Storage upload ───────────────────────────────────────

    def _upload_pdf(self, report_id: str, pdf_bytes: bytes) -> Optional[str]:
        """Upload PDF to Supabase Storage and return the public URL."""
        try:
            path = f"reports/{report_id}.pdf"
            self._db.storage.from_("report-pdfs").upload(
                path=path,
                file=pdf_bytes,
                file_options={"content-type": "application/pdf"},
            )
            url = self._db.storage.from_("report-pdfs").get_public_url(path)
            logger.info("PDF uploaded: %s", url)
            return url
        except Exception as exc:
            logger.error("PDF upload failed: %s", exc)
            return None
