/**
 * ClassPulse AI — Upstash Redis Client (Vercel Serverless Compatible)
 *
 * Replaces node-redis with Upstash REST-based Redis for edge/serverless.
 * Falls back gracefully when credentials are not set (local dev).
 */

import { Redis } from "@upstash/redis";

// ── Client ──────────────────────────────────────────────────

const redisUrl = process.env.UPSTASH_REDIS_REST_URL;
const redisToken = process.env.UPSTASH_REDIS_REST_TOKEN;

export const redis =
  redisUrl && redisToken
    ? new Redis({ url: redisUrl, token: redisToken })
    : null;

export function isRedisAvailable(): boolean {
  return redis !== null;
}

// ── Key builders ────────────────────────────────────────────

const key = {
  sessionMetrics: (sid: string) => `classpulse:session:${sid}:metrics`,
  engagement: (sid: string, studentId: string) =>
    `classpulse:session:${sid}:engagement:${studentId}`,
  engagementAll: (sid: string) => `classpulse:session:${sid}:engagement:*`,
  attendance: (sid: string) => `classpulse:session:${sid}:attendance`,
  alertQueue: (sid: string) => `classpulse:session:${sid}:alerts`,
};

// ── Types ───────────────────────────────────────────────────

export interface CachedMetrics {
  fps: number;
  latency_ms: number;
  detected_count: number;
  present_count: number;
  alert_count: number;
  avg_engagement: number;
  emotion_distribution: Record<string, number>;
  updated_at: number;
}

export interface CachedAlert {
  type: string;
  message: string;
  severity: string;
  student_id: string | null;
  timestamp: number;
}

// ── Session Metrics Cache (TTL: 5s) ─────────────────────────

export async function cacheSessionMetrics(
  sessionId: string,
  metrics: CachedMetrics,
  ttl = 5,
): Promise<void> {
  if (!redis) return;
  try {
    await redis.set(key.sessionMetrics(sessionId), JSON.stringify(metrics), {
      ex: ttl,
    });
  } catch (e) {
    console.error("[redis] cacheSessionMetrics error:", e);
  }
}

export async function getSessionMetrics(
  sessionId: string,
): Promise<CachedMetrics | null> {
  if (!redis) return null;
  try {
    const raw = await redis.get<string>(key.sessionMetrics(sessionId));
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    console.error("[redis] getSessionMetrics error:", e);
    return null;
  }
}

// ── Engagement Scores Cache (TTL: 10s) ──────────────────────

export async function cacheEngagementScore(
  sessionId: string,
  studentId: string,
  score: number,
  ttl = 10,
): Promise<void> {
  if (!redis) return;
  try {
    await redis.set(
      key.engagement(sessionId, studentId),
      JSON.stringify({ score, updated_at: Date.now() }),
      { ex: ttl },
    );
  } catch (e) {
    console.error("[redis] cacheEngagementScore error:", e);
  }
}

export async function getEngagementScore(
  sessionId: string,
  studentId: string,
): Promise<{ score: number; updated_at: number } | null> {
  if (!redis) return null;
  try {
    const raw = await redis.get<string>(
      key.engagement(sessionId, studentId),
    );
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    console.error("[redis] getEngagementScore error:", e);
    return null;
  }
}

// ── Alert Queue ─────────────────────────────────────────────

export async function publishAlert(
  sessionId: string,
  alert: CachedAlert,
): Promise<void> {
  if (!redis) return;
  try {
    // Push to a list, trim to 100 max, set TTL 1 hour
    const k = key.alertQueue(sessionId);
    await redis.lpush(k, JSON.stringify(alert));
    await redis.ltrim(k, 0, 99);
    await redis.expire(k, 3600);
  } catch (e) {
    console.error("[redis] publishAlert error:", e);
  }
}

export async function getAlerts(
  sessionId: string,
  count = 20,
): Promise<CachedAlert[]> {
  if (!redis) return [];
  try {
    const items = await redis.lrange(key.alertQueue(sessionId), 0, count - 1);
    return items.map((item) =>
      typeof item === "string" ? JSON.parse(item) : item,
    ) as CachedAlert[];
  } catch (e) {
    console.error("[redis] getAlerts error:", e);
    return [];
  }
}

// ── Attendance State (TTL: session duration) ────────────────

export async function cacheAttendance(
  sessionId: string,
  records: Record<string, { status: string; confidence: number }>,
  ttl = 14400, // 4 hours
): Promise<void> {
  if (!redis) return;
  try {
    await redis.set(key.attendance(sessionId), JSON.stringify(records), {
      ex: ttl,
    });
  } catch (e) {
    console.error("[redis] cacheAttendance error:", e);
  }
}

export async function getAttendance(
  sessionId: string,
): Promise<Record<string, { status: string; confidence: number }> | null> {
  if (!redis) return null;
  try {
    const raw = await redis.get<string>(key.attendance(sessionId));
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    console.error("[redis] getAttendance error:", e);
    return null;
  }
}
