"use client";

import { useEffect, useRef, useCallback, useState, useMemo } from "react";
import type {
  DetectedStudent,
  LiveMetrics,
  Alert,
  AttendanceRecord,
  AlertType,
  AlertSeverity,
  EmotionLabel,
  BBox,
} from "./types";

// ── Types ───────────────────────────────────────────────────

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "reconnecting" | "error";

export interface FrameUpdate {
  frame_b64: string;
  fps: number;
  timestamp: number;
}

export interface DetectionUpdate {
  students: DetectedStudent[];
  count: number;
}

export interface AlertEvent {
  type: AlertType;
  message: string;
  severity: AlertSeverity;
  student_id: string | null;
}

export interface AttendanceUpdate {
  student_id: string;
  status: "present" | "absent" | "late";
  confidence: number;
}

export interface MetricsUpdate {
  fps: number;
  latency_ms: number;
  detected_count: number;
  present_count: number;
  alert_count: number;
  avg_engagement: number;
  emotion_distribution: Record<string, number>;
}

export interface SessionUpdate {
  session_id: string;
  status: "active" | "completed" | "cancelled";
  started_at?: string;
  total_students?: number;
}

interface WSMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

// ── Singleton WebSocket Manager ─────────────────────────────

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/stream";

type Handler<T = unknown> = (data: T) => void;

class WebSocketManagerImpl {
  private static instance: WebSocketManagerImpl | null = null;
  private ws: WebSocket | null = null;
  private status: ConnectionStatus = "disconnected";
  private retries = 0;
  private maxRetries = 15;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingInterval: ReturnType<typeof setInterval> | null = null;
  private listeners = new Map<string, Set<Handler>>();
  private statusListeners = new Set<Handler<ConnectionStatus>>();

  static getInstance(): WebSocketManagerImpl {
    if (!WebSocketManagerImpl.instance) {
      WebSocketManagerImpl.instance = new WebSocketManagerImpl();
    }
    return WebSocketManagerImpl.instance;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) return;
    this.setStatus("connecting");

    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        this.setStatus("connected");
        this.retries = 0;
        this.startPing();
      };

      this.ws.onmessage = (e) => {
        try {
          const msg: WSMessage = JSON.parse(e.data);
          this.dispatch(msg.type, msg.data);
        } catch {
          /* ignore malformed */
        }
      };

      this.ws.onerror = () => {
        this.setStatus("error");
      };

      this.ws.onclose = (e) => {
        this.stopPing();
        this.ws = null;
        if (e.code !== 1000 && this.retries < this.maxRetries) {
          this.setStatus("reconnecting");
          const delay = Math.min(1000 * Math.pow(1.5, this.retries), 30000);
          this.retries++;
          this.reconnectTimer = setTimeout(() => this.connect(), delay);
        } else {
          this.setStatus("disconnected");
        }
      };
    } catch {
      this.setStatus("error");
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.stopPing();
    this.retries = this.maxRetries; // prevent reconnect
    this.ws?.close(1000);
    this.ws = null;
    this.setStatus("disconnected");
  }

  send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  joinSession(sessionId: string): void {
    this.send({ command: "join_session", session_id: sessionId });
  }

  startSession(sessionId: string): void {
    this.send({ command: "start_session", session_id: sessionId });
  }

  stopSession(): void {
    this.send({ command: "stop_session" });
  }

  // ── Event system ──────────────────────────────────────────

  on<T = unknown>(type: string, handler: Handler<T>): () => void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    const set = this.listeners.get(type)!;
    set.add(handler as Handler);
    return () => set.delete(handler as Handler);
  }

  onStatus(handler: Handler<ConnectionStatus>): () => void {
    this.statusListeners.add(handler);
    handler(this.status); // emit current
    return () => this.statusListeners.delete(handler);
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  private dispatch(type: string, data: unknown): void {
    this.listeners.get(type)?.forEach((h) => {
      try { h(data); } catch { /* handler error */ }
    });
  }

  private setStatus(s: ConnectionStatus): void {
    this.status = s;
    this.statusListeners.forEach((h) => {
      try { h(s); } catch { /* */ }
    });
  }

  private startPing(): void {
    this.pingInterval = setInterval(() => {
      this.send({ command: "ping" });
    }, 30_000);
  }

  private stopPing(): void {
    if (this.pingInterval) clearInterval(this.pingInterval);
    this.pingInterval = null;
  }
}

// ── Public accessor ─────────────────────────────────────────

export const wsManager = typeof window !== "undefined" ? WebSocketManagerImpl.getInstance() : null;

// ── Hook: useWebSocket ──────────────────────────────────────

export function useWebSocket() {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [lastFrame, setLastFrame] = useState<FrameUpdate | null>(null);
  const [detections, setDetections] = useState<DetectedStudent[]>([]);
  const [metrics, setMetrics] = useState<MetricsUpdate>({
    fps: 0, latency_ms: 0, detected_count: 0, present_count: 0,
    alert_count: 0, avg_engagement: 0, emotion_distribution: {},
  });
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [attendance, setAttendance] = useState<AttendanceUpdate[]>([]);
  const [session, setSession] = useState<SessionUpdate | null>(null);

  useEffect(() => {
    if (!wsManager) return;

    wsManager.connect();

    const unsubs = [
      wsManager.onStatus(setStatus),
      wsManager.on<FrameUpdate>("frame_update", setLastFrame),
      wsManager.on<DetectionUpdate>("detection_update", (d) => setDetections(d.students)),
      wsManager.on<MetricsUpdate>("metrics_update", setMetrics),
      wsManager.on<AlertEvent>("alert", (a) => setAlerts((prev) => [a, ...prev].slice(0, 50))),
      wsManager.on<AttendanceUpdate>("attendance_update", (a) =>
        setAttendance((prev) => {
          const idx = prev.findIndex((r) => r.student_id === a.student_id);
          if (idx >= 0) { const next = [...prev]; next[idx] = a; return next; }
          return [...prev, a];
        }),
      ),
      wsManager.on<SessionUpdate>("session_update", setSession),
    ];

    return () => { unsubs.forEach((u) => u()); };
  }, []);

  const send = useCallback((data: Record<string, unknown>) => wsManager?.send(data), []);
  const joinSession = useCallback((sid: string) => wsManager?.joinSession(sid), []);
  const startSession = useCallback((sid: string) => wsManager?.startSession(sid), []);
  const stopSession = useCallback(() => wsManager?.stopSession(), []);
  const disconnect = useCallback(() => wsManager?.disconnect(), []);

  return {
    isConnected: status === "connected",
    status,
    lastFrame,
    detections,
    metrics,
    alerts,
    attendance,
    session,
    send,
    joinSession,
    startSession,
    stopSession,
    disconnect,
  };
}

// ── Hook: useAlerts ─────────────────────────────────────────

export function useAlerts(autoDismissMs = 15_000) {
  const [alerts, setAlerts] = useState<(AlertEvent & { id: string; at: number; dismissed: boolean })[]>([]);

  useEffect(() => {
    if (!wsManager) return;
    let counter = 0;

    const unsub = wsManager.on<AlertEvent>("alert", (a) => {
      const id = `alert-${++counter}`;
      const entry = { ...a, id, at: Date.now(), dismissed: false };
      setAlerts((prev) => [entry, ...prev].slice(0, 100));

      if (autoDismissMs > 0) {
        setTimeout(() => {
          setAlerts((prev) => prev.map((x) => x.id === id ? { ...x, dismissed: true } : x));
        }, autoDismissMs);
      }
    });

    return unsub;
  }, [autoDismissMs]);

  const dismiss = useCallback((id: string) => {
    setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, dismissed: true } : a));
  }, []);

  const dismissAll = useCallback(() => {
    setAlerts((prev) => prev.map((a) => ({ ...a, dismissed: true })));
  }, []);

  const active = useMemo(() => alerts.filter((a) => !a.dismissed), [alerts]);
  const counts = useMemo(() => {
    const c = { low: 0, medium: 0, high: 0, critical: 0 };
    active.forEach((a) => { c[a.severity]++; });
    return c;
  }, [active]);

  return { alerts: active, all: alerts, dismiss, dismissAll, counts };
}

// ── Hook: useMetrics (rolling averages) ─────────────────────

export function useMetrics(windowSize = 30) {
  const history = useRef<MetricsUpdate[]>([]);
  const [current, setCurrent] = useState<MetricsUpdate>({
    fps: 0, latency_ms: 0, detected_count: 0, present_count: 0,
    alert_count: 0, avg_engagement: 0, emotion_distribution: {},
  });
  const [rolling, setRolling] = useState({
    avgFps: 0, avgLatency: 0, avgEngagement: 0, minEngagement: 0, maxEngagement: 0,
  });

  useEffect(() => {
    if (!wsManager) return;

    const unsub = wsManager.on<MetricsUpdate>("metrics_update", (m) => {
      setCurrent(m);
      history.current = [...history.current, m].slice(-windowSize);

      const h = history.current;
      const len = h.length || 1;
      setRolling({
        avgFps: h.reduce((s, x) => s + x.fps, 0) / len,
        avgLatency: h.reduce((s, x) => s + x.latency_ms, 0) / len,
        avgEngagement: h.reduce((s, x) => s + x.avg_engagement, 0) / len,
        minEngagement: Math.min(...h.map((x) => x.avg_engagement)),
        maxEngagement: Math.max(...h.map((x) => x.avg_engagement)),
      });
    });

    return unsub;
  }, [windowSize]);

  return { current, rolling, history: history.current };
}

// ── Simulated data for demo mode ────────────────────────────

function randBetween(a: number, b: number) {
  return a + Math.random() * (b - a);
}

function genHistory() {
  const d = [];
  const now = Date.now();
  for (let i = 29; i >= 0; i--)
    d.push({
      time: new Date(now - i * 60000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      avg: randBetween(55, 90),
      high: randBetween(80, 98),
      low: randBetween(20, 55),
    });
  return d;
}

export function useSimulatedData() {
  const [data, setData] = useState({
    totalStudents: 47,
    presentStudents: 43,
    avgEngagement: 76.4,
    alertsCount: 3,
    fps: 30,
    latency: 42,
    detectionCount: 43,
    emotions: {
      attentive: 18,
      engaged: 12,
      confused: 5,
      distracted: 5,
      sleepy: 3,
    } as Record<string, number>,
    engagementHistory: genHistory(),
    phoneDetections: 2,
    alerts: [
      { id: "1", type: "phone_detected" as const, message: "Phone detected near seat B3", severity: "medium" as const, created_at: new Date().toISOString(), is_resolved: false },
      { id: "2", type: "low_engagement" as const, message: "Class engagement dropped below 50%", severity: "high" as const, created_at: new Date(Date.now() - 300000).toISOString(), is_resolved: false },
      { id: "3", type: "mass_sleeping" as const, message: "3 students detected sleeping", severity: "critical" as const, created_at: new Date(Date.now() - 600000).toISOString(), is_resolved: true },
    ],
    recentSessions: [
      { id: "s1", class_name: "CS 101", date: "2026-05-04", students: 47, engagement: 78.5, status: "completed" },
      { id: "s2", class_name: "CS 101", date: "2026-05-02", students: 45, engagement: 82.1, status: "completed" },
      { id: "s3", class_name: "CS 101", date: "2026-04-30", students: 44, engagement: 71.3, status: "completed" },
      { id: "s4", class_name: "CS 101", date: "2026-04-28", students: 46, engagement: 85.2, status: "completed" },
    ],
  });

  useEffect(() => {
    const iv = setInterval(() => {
      setData((prev) => {
        const emo = { ...prev.emotions };
        const keys = Object.keys(emo);
        const k = keys[Math.floor(Math.random() * keys.length)];
        emo[k] = Math.max(0, emo[k] + (Math.random() > 0.5 ? 1 : -1));
        const newEng = Math.max(30, Math.min(98, prev.avgEngagement + (Math.random() - 0.5) * 4));
        return {
          ...prev,
          avgEngagement: newEng,
          emotions: emo,
          engagementHistory: [
            ...prev.engagementHistory.slice(1),
            {
              time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              avg: newEng,
              high: Math.min(100, newEng + randBetween(5, 20)),
              low: Math.max(10, newEng - randBetween(15, 35)),
            },
          ],
          fps: 28 + Math.floor(Math.random() * 4),
          latency: 35 + Math.floor(Math.random() * 20),
          detectionCount: 40 + Math.floor(Math.random() * 8),
        };
      });
    }, 2000);
    return () => clearInterval(iv);
  }, []);

  return data;
}
