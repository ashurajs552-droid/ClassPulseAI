"""
ClassPulse AI — WebSocket Connection Manager

Production-grade WebSocket manager with:
  - Multi-client support with per-session rooms
  - Typed message broadcasting (frame, detection, alert, attendance, metrics, session)
  - Heartbeat ping/pong every 30 seconds
  - Graceful disconnect with automatic cleanup
  - Frame-rate throttling to prevent client saturation
  - Thread-safe operations via asyncio locks
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


# ── Message types ────────────────────────────────────────────

class MessageType(str, Enum):
    FRAME_UPDATE = "frame_update"
    DETECTION_UPDATE = "detection_update"
    ALERT = "alert"
    ATTENDANCE_UPDATE = "attendance_update"
    METRICS_UPDATE = "metrics_update"
    SESSION_UPDATE = "session_update"
    PONG = "pong"
    ERROR = "error"
    ACK = "ack"


# ── Client metadata ─────────────────────────────────────────

@dataclass
class WSClient:
    """Represents a single connected WebSocket client."""
    ws: WebSocket
    client_id: str
    session_id: Optional[str] = None
    connected_at: float = field(default_factory=time.time)
    last_pong: float = field(default_factory=time.time)
    frames_sent: int = 0
    messages_sent: int = 0
    is_alive: bool = True


# ── Manager ──────────────────────────────────────────────────

class WebSocketManager:
    """
    Manages all WebSocket connections for the ClassPulse backend.

    Features:
      - Per-session rooms: clients join a session_id room to receive
        only that session's updates
      - Global broadcast: send to all connected clients
      - Heartbeat: pings every 30s, disconnects stale clients after 90s
      - Typed messages: every outbound message has {type, data, timestamp}
      - Throttled frame broadcasts: max 15 frame_update msgs/sec per client
    """

    def __init__(self, heartbeat_interval: float = 30.0, stale_timeout: float = 90.0) -> None:
        self._clients: dict[str, WSClient] = {}              # client_id → WSClient
        self._sessions: dict[str, set[str]] = defaultdict(set)  # session_id → {client_ids}
        self._lock = asyncio.Lock()
        self._heartbeat_interval = heartbeat_interval
        self._stale_timeout = stale_timeout
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

        # Throttle: last frame_update sent per client
        self._last_frame_ts: dict[str, float] = {}
        self._min_frame_interval = 1.0 / 15  # max 15 fps to clients

    # ── Lifecycle ────────────────────────────────────────────

    def start(self) -> None:
        """Start the heartbeat loop. Call once at app startup."""
        if not self._running:
            self._running = True
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("WebSocket manager started (heartbeat=%0.fs).", self._heartbeat_interval)

    async def shutdown(self) -> None:
        """Gracefully close all connections and stop heartbeat."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            for client in list(self._clients.values()):
                await self._safe_close(client)
            self._clients.clear()
            self._sessions.clear()

        logger.info("WebSocket manager shut down. All clients disconnected.")

    # ── Connect / Disconnect ─────────────────────────────────

    async def connect(self, ws: WebSocket, session_id: Optional[str] = None) -> str:
        """
        Accept a WebSocket connection, register client, return client_id.
        """
        await ws.accept()
        client_id = str(uuid.uuid4())[:12]
        client = WSClient(ws=ws, client_id=client_id, session_id=session_id)

        async with self._lock:
            self._clients[client_id] = client
            if session_id:
                self._sessions[session_id].add(client_id)

        logger.info(
            "WS client %s connected (session=%s). Total: %d",
            client_id, session_id or "global", len(self._clients),
        )

        # Send welcome ack
        await self._send_to_client(client, MessageType.ACK, {
            "client_id": client_id,
            "message": "Connected to ClassPulse AI",
            "session_id": session_id,
        })

        return client_id

    async def disconnect(self, client_id: str) -> None:
        """Remove a client by ID."""
        async with self._lock:
            client = self._clients.pop(client_id, None)
            if client:
                if client.session_id:
                    self._sessions[client.session_id].discard(client_id)
                    if not self._sessions[client.session_id]:
                        del self._sessions[client.session_id]
                self._last_frame_ts.pop(client_id, None)
                client.is_alive = False

        if client:
            logger.info(
                "WS client %s disconnected (sent %d msgs, %d frames). Total: %d",
                client_id, client.messages_sent, client.frames_sent, len(self._clients),
            )

    async def join_session(self, client_id: str, session_id: str) -> None:
        """Move a client into a session room."""
        async with self._lock:
            client = self._clients.get(client_id)
            if not client:
                return
            # Leave old session
            if client.session_id:
                self._sessions[client.session_id].discard(client_id)
                if not self._sessions[client.session_id]:
                    del self._sessions[client.session_id]
            # Join new session
            client.session_id = session_id
            self._sessions[session_id].add(client_id)

        logger.info("Client %s joined session %s", client_id, session_id)

    async def leave_session(self, client_id: str) -> None:
        """Remove a client from its session room (stays connected globally)."""
        async with self._lock:
            client = self._clients.get(client_id)
            if not client or not client.session_id:
                return
            self._sessions[client.session_id].discard(client_id)
            if not self._sessions[client.session_id]:
                del self._sessions[client.session_id]
            client.session_id = None

    # ── Broadcasting ─────────────────────────────────────────

    async def broadcast(self, msg_type: MessageType, data: dict[str, Any]) -> None:
        """Send a typed message to ALL connected clients."""
        dead: list[str] = []
        async with self._lock:
            clients = list(self._clients.values())

        for client in clients:
            if not await self._throttled_send(client, msg_type, data):
                dead.append(client.client_id)

        if dead:
            for cid in dead:
                await self.disconnect(cid)

    async def broadcast_to_session(
        self, session_id: str, msg_type: MessageType, data: dict[str, Any]
    ) -> None:
        """Send a typed message to all clients in a specific session room."""
        async with self._lock:
            client_ids = list(self._sessions.get(session_id, set()))

        dead: list[str] = []
        for cid in client_ids:
            client = self._clients.get(cid)
            if client:
                if not await self._throttled_send(client, msg_type, data):
                    dead.append(cid)

        if dead:
            for cid in dead:
                await self.disconnect(cid)

    async def send_to_client(self, client_id: str, msg_type: MessageType, data: dict[str, Any]) -> bool:
        """Send a typed message to a specific client."""
        client = self._clients.get(client_id)
        if not client:
            return False
        return await self._send_to_client(client, msg_type, data)

    # ── Typed broadcast helpers ──────────────────────────────

    async def broadcast_frame(self, session_id: str, frame_b64: str, fps: float, timestamp: float) -> None:
        """Broadcast a video frame to session clients (throttled)."""
        await self.broadcast_to_session(session_id, MessageType.FRAME_UPDATE, {
            "frame_b64": frame_b64,
            "fps": round(fps, 1),
            "timestamp": timestamp,
        })

    async def broadcast_detections(
        self,
        session_id: str,
        students: list[dict[str, Any]],
    ) -> None:
        """Broadcast detection updates to session clients."""
        await self.broadcast_to_session(session_id, MessageType.DETECTION_UPDATE, {
            "students": students,
            "count": len(students),
        })

    async def broadcast_alert(
        self,
        session_id: str,
        alert_type: str,
        message: str,
        severity: str,
        student_id: Optional[str] = None,
    ) -> None:
        """Broadcast an alert to session clients."""
        await self.broadcast_to_session(session_id, MessageType.ALERT, {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "student_id": student_id,
        })

    async def broadcast_attendance(
        self,
        session_id: str,
        student_id: str,
        status: str,
        confidence: float,
    ) -> None:
        """Broadcast an attendance update."""
        await self.broadcast_to_session(session_id, MessageType.ATTENDANCE_UPDATE, {
            "student_id": student_id,
            "status": status,
            "confidence": round(confidence, 4),
        })

    async def broadcast_metrics(
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
        """Broadcast session metrics update."""
        await self.broadcast_to_session(session_id, MessageType.METRICS_UPDATE, {
            "fps": round(fps, 1),
            "latency_ms": round(latency_ms, 1),
            "detected_count": detected_count,
            "present_count": present_count,
            "alert_count": alert_count,
            "avg_engagement": round(avg_engagement, 1),
            "emotion_distribution": emotion_distribution,
        })

    async def broadcast_session_update(
        self,
        session_id: str,
        status: str,
        started_at: Optional[str] = None,
        total_students: int = 0,
    ) -> None:
        """Broadcast session state change."""
        await self.broadcast_to_session(session_id, MessageType.SESSION_UPDATE, {
            "session_id": session_id,
            "status": status,
            "started_at": started_at,
            "total_students": total_students,
        })

    # ── Incoming message handler ─────────────────────────────

    async def handle_client_message(
        self, client_id: str, raw: str
    ) -> Optional[dict[str, Any]]:
        """
        Parse and handle an incoming client message.
        Returns a parsed dict for the caller to act on, or None if handled internally.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self.send_to_client(client_id, MessageType.ERROR, {
                "message": "Invalid JSON",
            })
            return None

        cmd = data.get("command") or data.get("type")

        if cmd == "ping":
            client = self._clients.get(client_id)
            if client:
                client.last_pong = time.time()
            await self.send_to_client(client_id, MessageType.PONG, {
                "server_time": time.time(),
            })
            return None

        if cmd == "join_session":
            sid = data.get("session_id")
            if sid:
                await self.join_session(client_id, sid)
                await self.send_to_client(client_id, MessageType.ACK, {
                    "message": f"Joined session {sid}",
                    "session_id": sid,
                })
            return None

        if cmd == "leave_session":
            await self.leave_session(client_id)
            await self.send_to_client(client_id, MessageType.ACK, {
                "message": "Left session",
            })
            return None

        # Return unhandled messages for the caller (e.g. start_session, stop_session)
        return data

    # ── Heartbeat ────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        """Periodically ping all clients and prune stale ones."""
        while self._running:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                now = time.time()
                stale: list[str] = []

                async with self._lock:
                    clients = list(self._clients.values())

                for client in clients:
                    if now - client.last_pong > self._stale_timeout:
                        stale.append(client.client_id)
                        logger.warning(
                            "Client %s stale (last pong %.0fs ago), removing.",
                            client.client_id, now - client.last_pong,
                        )
                    else:
                        try:
                            await client.ws.send_json({
                                "type": "ping",
                                "timestamp": now,
                            })
                        except Exception:
                            stale.append(client.client_id)

                for cid in stale:
                    await self.disconnect(cid)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Heartbeat error: %s", exc)

    # ── Internal send helpers ────────────────────────────────

    async def _send_to_client(
        self, client: WSClient, msg_type: MessageType, data: dict[str, Any]
    ) -> bool:
        """Send a typed JSON envelope to a single client. Returns False if dead."""
        if not client.is_alive:
            return False
        try:
            payload = {
                "type": msg_type.value,
                "data": data,
                "timestamp": time.time(),
            }
            await client.ws.send_json(payload)
            client.messages_sent += 1
            if msg_type == MessageType.FRAME_UPDATE:
                client.frames_sent += 1
            return True
        except Exception:
            client.is_alive = False
            return False

    async def _throttled_send(
        self, client: WSClient, msg_type: MessageType, data: dict[str, Any]
    ) -> bool:
        """
        Send with frame-rate throttling for FRAME_UPDATE messages.
        Other message types are sent immediately.
        """
        if msg_type == MessageType.FRAME_UPDATE:
            now = time.time()
            last = self._last_frame_ts.get(client.client_id, 0)
            if now - last < self._min_frame_interval:
                return True  # throttled, not dead
            self._last_frame_ts[client.client_id] = now

        return await self._send_to_client(client, msg_type, data)

    async def _safe_close(self, client: WSClient) -> None:
        """Close a client connection without raising."""
        try:
            await client.ws.close()
        except Exception:
            pass
        client.is_alive = False

    # ── Stats ────────────────────────────────────────────────

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def get_stats(self) -> dict[str, Any]:
        """Return manager statistics for health endpoints."""
        return {
            "total_clients": self.client_count,
            "active_sessions": self.session_count,
            "sessions": {
                sid: len(clients) for sid, clients in self._sessions.items()
            },
            "clients": [
                {
                    "id": c.client_id,
                    "session": c.session_id,
                    "connected_seconds": round(time.time() - c.connected_at),
                    "messages_sent": c.messages_sent,
                    "frames_sent": c.frames_sent,
                    "alive": c.is_alive,
                }
                for c in self._clients.values()
            ],
        }
