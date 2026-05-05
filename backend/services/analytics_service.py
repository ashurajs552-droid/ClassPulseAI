"""
ClassPulse AI — Analytics Service

Aggregates session data from Supabase for dashboard metrics:
attendance %, average engagement, emotion breakdown, and anomaly detection.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from config import settings

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Aggregation and anomaly detection across session data."""

    def __init__(self, supabase_client=None) -> None:
        self._db = supabase_client
        self._loaded = False

    def load(self, supabase_client=None) -> None:
        """Set the Supabase client."""
        if supabase_client:
            self._db = supabase_client
        self._loaded = True
        logger.info("Analytics service loaded.")

    def unload(self) -> None:
        self._db = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Session metrics ──────────────────────────────────────

    def get_session_metrics(self, session_id: str) -> dict[str, Any]:
        """
        Aggregate all metrics for a given session.

        Returns:
            {
                attendance_rate, total_students, present_count,
                avg_engagement, emotion_distribution,
                phone_detections, alerts_count, alert_breakdown,
                duration_minutes
            }
        """
        if not self._db:
            return self._empty_metrics()

        try:
            # Session info
            session = (
                self._db.table("sessions")
                .select("*")
                .eq("id", session_id)
                .single()
                .execute()
            )
            sess_data = session.data or {}

            total = sess_data.get("total_students", 0)

            # Attendance
            att_resp = (
                self._db.table("attendance")
                .select("id, status")
                .eq("session_id", session_id)
                .execute()
            )
            att_records = att_resp.data or []
            present = sum(1 for r in att_records if r["status"] in ("present", "late"))
            att_rate = (present / total * 100) if total > 0 else 0.0

            # Engagement scores
            eng_resp = (
                self._db.table("engagement_scores")
                .select("score")
                .eq("session_id", session_id)
                .execute()
            )
            eng_scores = [r["score"] for r in (eng_resp.data or []) if r.get("score") is not None]
            avg_eng = sum(eng_scores) / len(eng_scores) if eng_scores else 0.0

            # Emotion distribution
            emo_resp = (
                self._db.table("emotion_logs")
                .select("emotion")
                .eq("session_id", session_id)
                .execute()
            )
            emo_dist: dict[str, int] = {}
            for r in emo_resp.data or []:
                e = r.get("emotion", "unknown")
                emo_dist[e] = emo_dist.get(e, 0) + 1

            # Phone detections
            phone_resp = (
                self._db.table("phone_detections")
                .select("id")
                .eq("session_id", session_id)
                .execute()
            )
            phone_count = len(phone_resp.data or [])

            # Alerts
            alerts_resp = (
                self._db.table("alerts")
                .select("type, severity, is_resolved")
                .eq("session_id", session_id)
                .execute()
            )
            alerts = alerts_resp.data or []
            alert_breakdown: dict[str, int] = {}
            for a in alerts:
                t = a.get("type", "unknown")
                alert_breakdown[t] = alert_breakdown.get(t, 0) + 1

            # Duration
            started = sess_data.get("started_at")
            ended = sess_data.get("ended_at")
            duration = 0.0
            if started and ended:
                try:
                    s = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    e = datetime.fromisoformat(ended.replace("Z", "+00:00"))
                    duration = (e - s).total_seconds() / 60
                except Exception:
                    pass

            return {
                "session_id": session_id,
                "attendance_rate": round(att_rate, 1),
                "total_students": total,
                "present_count": present,
                "absent_count": total - present,
                "avg_engagement": round(avg_eng, 1),
                "emotion_distribution": emo_dist,
                "phone_detections": phone_count,
                "alerts_count": len(alerts),
                "alerts_unresolved": sum(1 for a in alerts if not a.get("is_resolved")),
                "alert_breakdown": alert_breakdown,
                "duration_minutes": round(duration, 1),
                "status": sess_data.get("status", "unknown"),
            }

        except Exception as exc:
            logger.exception("Failed to compute session metrics: %s", exc)
            return self._empty_metrics()

    # ── Trend data ───────────────────────────────────────────

    def get_engagement_trend(
        self,
        session_id: str,
        bucket_minutes: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Return engagement scores bucketed by time for charting.
        """
        if not self._db:
            return []

        try:
            resp = (
                self._db.table("engagement_scores")
                .select("score, timestamp")
                .eq("session_id", session_id)
                .order("timestamp", desc=False)
                .execute()
            )
            rows = resp.data or []
            if not rows:
                return []

            # Bucket
            buckets: dict[str, list[float]] = {}
            for r in rows:
                ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                bucket_key = ts.strftime("%H:%M")
                buckets.setdefault(bucket_key, []).append(r["score"])

            return [
                {"time": k, "score": round(sum(v) / len(v), 1)}
                for k, v in buckets.items()
            ]

        except Exception as exc:
            logger.error("Engagement trend query failed: %s", exc)
            return []

    def get_per_student_engagement(self, session_id: str) -> list[dict[str, Any]]:
        """Return average engagement per student for a session."""
        if not self._db:
            return []

        try:
            resp = (
                self._db.table("engagement_scores")
                .select("student_id, score")
                .eq("session_id", session_id)
                .execute()
            )
            rows = resp.data or []

            student_scores: dict[str, list[float]] = {}
            for r in rows:
                sid = r.get("student_id")
                if sid:
                    student_scores.setdefault(sid, []).append(r["score"])

            # Fetch student names
            student_ids = list(student_scores.keys())
            names: dict[str, str] = {}
            if student_ids:
                name_resp = (
                    self._db.table("students")
                    .select("id, full_name")
                    .in_("id", student_ids)
                    .execute()
                )
                for r in name_resp.data or []:
                    names[r["id"]] = r["full_name"]

            return [
                {
                    "student_id": sid,
                    "student_name": names.get(sid, "Unknown"),
                    "avg_engagement": round(sum(scores) / len(scores), 1),
                    "data_points": len(scores),
                }
                for sid, scores in student_scores.items()
            ]

        except Exception as exc:
            logger.error("Per-student engagement query failed: %s", exc)
            return []

    # ── Anomaly detection ────────────────────────────────────

    def detect_anomalies(
        self,
        emotion_distribution: dict[str, int],
        avg_engagement: float,
    ) -> list[dict[str, str]]:
        """
        Detect classroom-level anomalies from current metrics.
        Returns a list of alert dicts: [{type, message, severity}]
        """
        anomalies: list[dict[str, str]] = []
        total = sum(emotion_distribution.values()) or 1

        # Mass sleeping
        sleepy = emotion_distribution.get("sleepy", 0)
        if sleepy / total > 0.15:
            anomalies.append({
                "type": "mass_sleeping",
                "message": f"{sleepy} students detected sleeping ({sleepy/total:.0%} of class)",
                "severity": "critical" if sleepy / total > 0.25 else "high",
            })

        # High confusion
        confused = emotion_distribution.get("confused", 0)
        if confused / total > 0.30:
            anomalies.append({
                "type": "high_confusion",
                "message": f"{confused} students appear confused ({confused/total:.0%} of class)",
                "severity": "high",
            })

        # Low engagement
        if avg_engagement < 40:
            anomalies.append({
                "type": "low_engagement",
                "message": f"Class engagement critically low at {avg_engagement:.0f}%",
                "severity": "critical" if avg_engagement < 25 else "high",
            })
        elif avg_engagement < 55:
            anomalies.append({
                "type": "low_engagement",
                "message": f"Class engagement below average at {avg_engagement:.0f}%",
                "severity": "medium",
            })

        return anomalies

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _empty_metrics() -> dict[str, Any]:
        return {
            "session_id": "",
            "attendance_rate": 0.0,
            "total_students": 0,
            "present_count": 0,
            "absent_count": 0,
            "avg_engagement": 0.0,
            "emotion_distribution": {},
            "phone_detections": 0,
            "alerts_count": 0,
            "alerts_unresolved": 0,
            "alert_breakdown": {},
            "duration_minutes": 0.0,
            "status": "unknown",
        }
