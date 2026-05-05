"""
ClassPulse AI — Redis Service

Provides:
  - Async Redis client with connection pooling
  - Session metrics cache (TTL: 5s) — hot path for dashboard polling
  - Student engagement scores cache (TTL: 10s) — per-student score map
  - Attendance state cache (TTL: session duration) — live attendance map
  - Pub/Sub channels for internal service communication
  - Helper methods for atomic read/write of structured data
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Optional

import redis.asyncio as aioredis
from redis.asyncio.client import PubSub

from config import settings

logger = logging.getLogger(__name__)

# ── Key prefixes ─────────────────────────────────────────────
PREFIX = "classpulse"
KEY_SESSION_METRICS = f"{PREFIX}:session:{{sid}}:metrics"         # TTL 5s
KEY_STUDENT_ENGAGEMENT = f"{PREFIX}:session:{{sid}}:engagement"   # TTL 10s
KEY_ATTENDANCE = f"{PREFIX}:session:{{sid}}:attendance"            # TTL session
KEY_SESSION_STATE = f"{PREFIX}:session:{{sid}}:state"              # TTL session
KEY_FRAME_COUNTER = f"{PREFIX}:session:{{sid}}:frames"            # TTL session
KEY_ACTIVE_SESSIONS = f"{PREFIX}:active_sessions"                  # SET

# ── Pub/Sub channels ────────────────────────────────────────
CHANNEL_ALERTS = f"{PREFIX}:alerts"
CHANNEL_DETECTIONS = f"{PREFIX}:detections"
CHANNEL_ATTENDANCE = f"{PREFIX}:attendance"
CHANNEL_SESSION = f"{PREFIX}:session_events"


class RedisService:
    """Async Redis service for caching and pub/sub."""

    def __init__(self) -> None:
        self._client: Optional[aioredis.Redis] = None
        self._pubsub: Optional[PubSub] = None
        self._subscriber_task: Optional[asyncio.Task] = None
        self._handlers: dict[str, list[Callable]] = {}
        self._loaded = False

    # ── Lifecycle ────────────────────────────────────────────

    async def connect(self, url: Optional[str] = None) -> bool:
        """
        Connect to Redis with automatic retry.
        Returns True if connected, False if Redis is unavailable.
        """
        redis_url = url or settings.redis_url
        try:
            self._client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                max_connections=20,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            await self._client.ping()
            self._loaded = True
            logger.info("✓ Redis connected: %s", redis_url)
            return True
        except Exception as exc:
            logger.warning("⚠ Redis unavailable (%s) — running without cache.", exc)
            self._client = None
            self._loaded = False
            return False

    async def disconnect(self) -> None:
        """Close Redis connection and stop subscriber."""
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        if self._client:
            await self._client.close()

        self._loaded = False
        logger.info("Redis disconnected.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def client(self) -> Optional[aioredis.Redis]:
        return self._client

    # ── Session Metrics Cache (TTL: 5s) ──────────────────────

    async def update_metrics(
        self,
        session_id: str,
        fps: float,
        latency_ms: float,
        detected_count: int,
        present_count: int,
        alert_count: int,
        avg_engagement: float,
        emotion_distribution: dict[str, int],
    ) -> None:
        """Cache the latest session metrics snapshot."""
        if not self._client:
            return

        key = KEY_SESSION_METRICS.format(sid=session_id)
        data = {
            "fps": fps,
            "latency_ms": latency_ms,
            "detected_count": detected_count,
            "present_count": present_count,
            "alert_count": alert_count,
            "avg_engagement": avg_engagement,
            "emotion_distribution": json.dumps(emotion_distribution),
            "updated_at": time.time(),
        }
        try:
            await self._client.hset(key, mapping=data)
            await self._client.expire(key, 5)
        except Exception as exc:
            logger.error("Redis metrics update failed: %s", exc)

    async def get_metrics(self, session_id: str) -> Optional[dict[str, Any]]:
        """Retrieve cached session metrics."""
        if not self._client:
            return None

        key = KEY_SESSION_METRICS.format(sid=session_id)
        try:
            data = await self._client.hgetall(key)
            if not data:
                return None
            # Parse numeric fields
            return {
                "fps": float(data.get("fps", 0)),
                "latency_ms": float(data.get("latency_ms", 0)),
                "detected_count": int(data.get("detected_count", 0)),
                "present_count": int(data.get("present_count", 0)),
                "alert_count": int(data.get("alert_count", 0)),
                "avg_engagement": float(data.get("avg_engagement", 0)),
                "emotion_distribution": json.loads(data.get("emotion_distribution", "{}")),
                "updated_at": float(data.get("updated_at", 0)),
            }
        except Exception as exc:
            logger.error("Redis metrics read failed: %s", exc)
            return None

    # ── Student Engagement Cache (TTL: 10s) ──────────────────

    async def update_engagement(
        self,
        session_id: str,
        student_id: str,
        score: float,
        attention: float = 0.0,
        emotion: str = "",
    ) -> None:
        """Cache a student's latest engagement score."""
        if not self._client:
            return

        key = KEY_STUDENT_ENGAGEMENT.format(sid=session_id)
        try:
            value = json.dumps({
                "score": score,
                "attention": attention,
                "emotion": emotion,
                "updated_at": time.time(),
            })
            await self._client.hset(key, student_id, value)
            await self._client.expire(key, 10)
        except Exception as exc:
            logger.error("Redis engagement update failed: %s", exc)

    async def get_engagement(
        self, session_id: str, student_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Retrieve engagement scores.
        If student_id given, returns that student's data.
        Otherwise returns all students' scores.
        """
        if not self._client:
            return {}

        key = KEY_STUDENT_ENGAGEMENT.format(sid=session_id)
        try:
            if student_id:
                raw = await self._client.hget(key, student_id)
                return json.loads(raw) if raw else {}
            else:
                raw_all = await self._client.hgetall(key)
                return {
                    sid: json.loads(val) for sid, val in raw_all.items()
                }
        except Exception as exc:
            logger.error("Redis engagement read failed: %s", exc)
            return {}

    async def get_engagement_batch(self, session_id: str) -> list[dict[str, Any]]:
        """Get all student engagement scores as a flat list."""
        data = await self.get_engagement(session_id)
        result = []
        for sid, info in data.items():
            result.append({
                "student_id": sid,
                "score": info.get("score", 0),
                "attention": info.get("attention", 0),
                "emotion": info.get("emotion", ""),
            })
        return sorted(result, key=lambda x: x["score"], reverse=True)

    # ── Attendance Cache (TTL: session duration) ─────────────

    async def update_attendance(
        self,
        session_id: str,
        student_id: str,
        status: str,
        confidence: float,
        detected_at: Optional[str] = None,
    ) -> None:
        """Cache a student's attendance state."""
        if not self._client:
            return

        key = KEY_ATTENDANCE.format(sid=session_id)
        try:
            value = json.dumps({
                "status": status,
                "confidence": confidence,
                "detected_at": detected_at or "",
                "updated_at": time.time(),
            })
            await self._client.hset(key, student_id, value)
            # Keep attendance for up to 4 hours
            await self._client.expire(key, 14400)
        except Exception as exc:
            logger.error("Redis attendance update failed: %s", exc)

    async def get_attendance(self, session_id: str) -> dict[str, Any]:
        """Retrieve all attendance records for a session."""
        if not self._client:
            return {}

        key = KEY_ATTENDANCE.format(sid=session_id)
        try:
            raw = await self._client.hgetall(key)
            return {sid: json.loads(val) for sid, val in raw.items()}
        except Exception as exc:
            logger.error("Redis attendance read failed: %s", exc)
            return {}

    # ── Session State ────────────────────────────────────────

    async def set_session_state(
        self,
        session_id: str,
        status: str,
        started_at: Optional[str] = None,
        total_students: int = 0,
        metadata: Optional[dict] = None,
    ) -> None:
        """Store the current session state."""
        if not self._client:
            return

        key = KEY_SESSION_STATE.format(sid=session_id)
        try:
            data = {
                "status": status,
                "started_at": started_at or "",
                "total_students": total_students,
                "metadata": json.dumps(metadata or {}),
                "updated_at": time.time(),
            }
            await self._client.hset(key, mapping=data)
            await self._client.expire(key, 14400)

            # Track active sessions
            if status == "active":
                await self._client.sadd(KEY_ACTIVE_SESSIONS, session_id)
            else:
                await self._client.srem(KEY_ACTIVE_SESSIONS, session_id)
        except Exception as exc:
            logger.error("Redis session state failed: %s", exc)

    async def get_session_state(self, session_id: str) -> Optional[dict[str, Any]]:
        """Retrieve session state from cache."""
        if not self._client:
            return None

        key = KEY_SESSION_STATE.format(sid=session_id)
        try:
            data = await self._client.hgetall(key)
            if not data:
                return None
            return {
                "status": data.get("status", "unknown"),
                "started_at": data.get("started_at", ""),
                "total_students": int(data.get("total_students", 0)),
                "metadata": json.loads(data.get("metadata", "{}")),
                "updated_at": float(data.get("updated_at", 0)),
            }
        except Exception as exc:
            logger.error("Redis session state read failed: %s", exc)
            return None

    async def get_active_sessions(self) -> list[str]:
        """List all currently active session IDs."""
        if not self._client:
            return []
        try:
            return list(await self._client.smembers(KEY_ACTIVE_SESSIONS))
        except Exception:
            return []

    # ── Frame Counter ────────────────────────────────────────

    async def increment_frame(self, session_id: str) -> int:
        """Increment and return the frame counter for a session."""
        if not self._client:
            return 0
        key = KEY_FRAME_COUNTER.format(sid=session_id)
        try:
            count = await self._client.incr(key)
            await self._client.expire(key, 14400)
            return count
        except Exception:
            return 0

    # ── Pub/Sub ──────────────────────────────────────────────

    async def publish(self, channel: str, data: dict[str, Any]) -> None:
        """Publish a message to a Redis channel."""
        if not self._client:
            return
        try:
            await self._client.publish(channel, json.dumps(data, default=str))
        except Exception as exc:
            logger.error("Redis publish failed on %s: %s", channel, exc)

    async def publish_alert(
        self,
        session_id: str,
        alert_type: str,
        message: str,
        severity: str,
        student_id: Optional[str] = None,
    ) -> None:
        """Publish an alert via Pub/Sub."""
        await self.publish(CHANNEL_ALERTS, {
            "session_id": session_id,
            "type": alert_type,
            "message": message,
            "severity": severity,
            "student_id": student_id,
            "timestamp": time.time(),
        })

    async def publish_detection(
        self, session_id: str, detections: list[dict[str, Any]]
    ) -> None:
        """Publish detection results via Pub/Sub."""
        await self.publish(CHANNEL_DETECTIONS, {
            "session_id": session_id,
            "detections": detections,
            "count": len(detections),
            "timestamp": time.time(),
        })

    async def subscribe(
        self,
        channel: str,
        handler: Callable[[dict[str, Any]], Coroutine],
    ) -> None:
        """Register an async handler for a Pub/Sub channel."""
        if channel not in self._handlers:
            self._handlers[channel] = []
        self._handlers[channel].append(handler)

        # Start subscriber task if not running
        if not self._subscriber_task or self._subscriber_task.done():
            self._subscriber_task = asyncio.create_task(self._subscriber_loop())

    async def _subscriber_loop(self) -> None:
        """Listen for Pub/Sub messages and dispatch to handlers."""
        if not self._client:
            return

        try:
            self._pubsub = self._client.pubsub()
            channels = list(self._handlers.keys())
            if channels:
                await self._pubsub.subscribe(*channels)
                logger.info("Redis Pub/Sub subscribed to: %s", channels)

            async for message in self._pubsub.listen():
                if message["type"] != "message":
                    continue

                channel = message["channel"]
                try:
                    data = json.loads(message["data"])
                except json.JSONDecodeError:
                    continue

                handlers = self._handlers.get(channel, [])
                for handler in handlers:
                    try:
                        await handler(data)
                    except Exception as exc:
                        logger.error("Pub/Sub handler error on %s: %s", channel, exc)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Pub/Sub subscriber loop error: %s", exc)

    # ── Cleanup ──────────────────────────────────────────────

    async def cleanup_session(self, session_id: str) -> None:
        """Remove all cached data for a completed session."""
        if not self._client:
            return

        keys = [
            KEY_SESSION_METRICS.format(sid=session_id),
            KEY_STUDENT_ENGAGEMENT.format(sid=session_id),
            KEY_ATTENDANCE.format(sid=session_id),
            KEY_SESSION_STATE.format(sid=session_id),
            KEY_FRAME_COUNTER.format(sid=session_id),
        ]
        try:
            await self._client.delete(*keys)
            await self._client.srem(KEY_ACTIVE_SESSIONS, session_id)
            logger.info("Cleaned up Redis cache for session %s", session_id)
        except Exception as exc:
            logger.error("Session cleanup failed: %s", exc)

    # ── Health ───────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Return Redis health info."""
        if not self._client:
            return {"status": "disconnected"}
        try:
            info = await self._client.info("server")
            return {
                "status": "connected",
                "redis_version": info.get("redis_version", "unknown"),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "active_sessions": len(await self.get_active_sessions()),
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
