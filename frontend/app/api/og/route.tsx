import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";

/**
 * GET /api/og?title=...&subtitle=...
 *
 * Dynamic OG image generation for ClassPulse AI.
 * Uses Vercel's @vercel/og (built into Next.js) for edge-rendered images.
 */

export const runtime = "edge";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const title = searchParams.get("title") || "ClassPulse AI";
  const subtitle =
    searchParams.get("subtitle") || "AI-Powered Classroom Monitoring";
  const stat1 = searchParams.get("stat1") || "";
  const stat2 = searchParams.get("stat2") || "";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          background: "linear-gradient(135deg, #0a0a0f 0%, #0f1117 50%, #0a0a0f 100%)",
          fontFamily: "Inter, sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Grid overlay */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage:
              "linear-gradient(rgba(99,102,241,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.04) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />

        {/* Glow orb */}
        <div
          style={{
            position: "absolute",
            width: 400,
            height: 400,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(99,102,241,0.15), transparent 70%)",
            top: -100,
            right: -100,
          }}
        />

        {/* Logo */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 80,
            height: 80,
            borderRadius: 20,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            marginBottom: 24,
            boxShadow: "0 0 60px rgba(99,102,241,0.4)",
          }}
        >
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        </div>

        {/* Title */}
        <div
          style={{
            display: "flex",
            fontSize: 48,
            fontWeight: 800,
            background: "linear-gradient(90deg, #818cf8, #a78bfa, #22d3ee)",
            backgroundClip: "text",
            color: "transparent",
            lineHeight: 1.1,
            textAlign: "center",
            maxWidth: "80%",
          }}
        >
          {title}
        </div>

        {/* Subtitle */}
        <div
          style={{
            fontSize: 20,
            color: "#64748b",
            marginTop: 12,
            textAlign: "center",
          }}
        >
          {subtitle}
        </div>

        {/* Stats row */}
        {(stat1 || stat2) && (
          <div
            style={{
              display: "flex",
              gap: 32,
              marginTop: 32,
              padding: "12px 24px",
              borderRadius: 12,
              border: "1px solid rgba(255,255,255,0.08)",
              background: "rgba(255,255,255,0.03)",
            }}
          >
            {stat1 && (
              <div style={{ fontSize: 16, color: "#94a3b8" }}>{stat1}</div>
            )}
            {stat2 && (
              <div style={{ fontSize: 16, color: "#94a3b8" }}>{stat2}</div>
            )}
          </div>
        )}

        {/* Bottom branding */}
        <div
          style={{
            position: "absolute",
            bottom: 24,
            fontSize: 14,
            color: "#334155",
          }}
        >
          classpulse-ai.vercel.app
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
    },
  );
}
