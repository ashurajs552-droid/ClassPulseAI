import { NextResponse } from "next/server";

/**
 * GET /api/health
 *
 * Checks connectivity to all external services:
 *  - Supabase (database)
 *  - Backend API (Railway)
 *  - Upstash Redis
 */

export const runtime = "edge";

export async function GET() {
  const t0 = Date.now();
  const services: Record<string, { status: string; latency_ms?: number; error?: string }> = {};

  // ── Supabase ──────────────────────────────────────────────
  try {
    const st = Date.now();
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_SUPABASE_URL}/rest/v1/`,
      {
        headers: {
          apikey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "",
          Authorization: `Bearer ${process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ""}`,
        },
        signal: AbortSignal.timeout(5000),
      },
    );
    services.supabase = {
      status: res.ok ? "healthy" : "degraded",
      latency_ms: Date.now() - st,
    };
  } catch (e: unknown) {
    services.supabase = {
      status: "unreachable",
      error: e instanceof Error ? e.message : "Unknown error",
    };
  }

  // ── Backend API (Railway) ─────────────────────────────────
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (apiUrl) {
      const st = Date.now();
      const res = await fetch(`${apiUrl}/health`, {
        signal: AbortSignal.timeout(5000),
      });
      const data = await res.json();
      services.backend = {
        status: data.status || (res.ok ? "healthy" : "degraded"),
        latency_ms: Date.now() - st,
      };
    } else {
      services.backend = { status: "not_configured" };
    }
  } catch (e: unknown) {
    services.backend = {
      status: "unreachable",
      error: e instanceof Error ? e.message : "Unknown error",
    };
  }

  // ── Upstash Redis ─────────────────────────────────────────
  try {
    const redisUrl = process.env.UPSTASH_REDIS_REST_URL;
    const redisToken = process.env.UPSTASH_REDIS_REST_TOKEN;
    if (redisUrl && redisToken) {
      const st = Date.now();
      const res = await fetch(`${redisUrl}/ping`, {
        headers: { Authorization: `Bearer ${redisToken}` },
        signal: AbortSignal.timeout(3000),
      });
      services.redis = {
        status: res.ok ? "healthy" : "degraded",
        latency_ms: Date.now() - st,
      };
    } else {
      services.redis = { status: "not_configured" };
    }
  } catch (e: unknown) {
    services.redis = {
      status: "unreachable",
      error: e instanceof Error ? e.message : "Unknown error",
    };
  }

  // ── Aggregate ─────────────────────────────────────────────
  const allHealthy = Object.values(services).every(
    (s) => s.status === "healthy" || s.status === "not_configured",
  );

  return NextResponse.json(
    {
      status: allHealthy ? "healthy" : "degraded",
      services,
      total_latency_ms: Date.now() - t0,
      timestamp: new Date().toISOString(),
      version: process.env.NEXT_PUBLIC_APP_VERSION || "1.0.0",
    },
    { status: allHealthy ? 200 : 503 },
  );
}
