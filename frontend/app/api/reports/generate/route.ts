import { NextResponse, type NextRequest } from "next/server";

/**
 * POST /api/reports/generate
 *
 * Vercel serverless function that proxies report generation to the
 * Railway backend.  Handles:
 *  - Auth validation (Supabase JWT from cookie)
 *  - Request forwarding to Railway
 *  - 30-second timeout (Vercel serverless max for hobby)
 *  - Error handling with structured responses
 */

export const maxDuration = 30; // Vercel Pro: up to 300s

export async function POST(request: NextRequest) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  if (!apiUrl) {
    return NextResponse.json(
      { error: "Backend API not configured" },
      { status: 503 },
    );
  }

  try {
    const body = await request.json();

    // Forward to Railway backend
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 28_000); // 28s to leave 2s buffer

    const response = await fetch(`${apiUrl}/api/reports/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Forward auth cookie if present
        ...(request.headers.get("authorization")
          ? { Authorization: request.headers.get("authorization")! }
          : {}),
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    const data = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch (error: unknown) {
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json(
        { error: "Report generation timed out. Try again or use a shorter session." },
        { status: 504 },
      );
    }

    return NextResponse.json(
      { error: "Failed to generate report", details: error instanceof Error ? error.message : "Unknown" },
      { status: 500 },
    );
  }
}
