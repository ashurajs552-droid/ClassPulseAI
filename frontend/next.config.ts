import type { NextConfig } from "next";

/**
 * ClassPulse AI — Next.js Configuration
 *
 * Handles:
 *  - Supabase image CDN domains
 *  - API proxy rewrites to Railway backend
 *  - Bundle analysis (opt-in via ANALYZE=true)
 *  - Strict React mode
 *  - Production environment validation
 */

const nextConfig: NextConfig = {
  reactStrictMode: true,

  webpack: (config: any) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      '@tensorflow/tfjs$': '@tensorflow/tfjs/dist/tf.min.js'
    }
    return config
  },

  // ── Image optimization ──────────────────────────────────────
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.supabase.co",
        pathname: "/storage/v1/object/public/**",
      },
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com", // Google OAuth avatars
      },
    ],
  },

  // ── API rewrites — proxy /api/backend/* to Railway ─────────
  async rewrites() {
    const backendUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },

  // ── Security headers ────────────────────────────────────────
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-DNS-Prefetch-Control", value: "on" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=*, microphone=*" },
          { key: "Feature-Policy", value: "camera *; microphone *" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          { key: "Cross-Origin-Embedder-Policy", value: "require-corp" }
        ],
      },
    ];
  },

  // ── Experimental ────────────────────────────────────────────
  experimental: {
    optimizePackageImports: ["lucide-react", "framer-motion", "recharts"],
  },

  // ── Environment validation (build-time) ─────────────────────
  env: {
    NEXT_PUBLIC_APP_VERSION: process.env.npm_package_version || "1.0.0",
  },

  // ── Logging ─────────────────────────────────────────────────
  logging: {
    fetches: {
      fullUrl: true,
    },
  },
};

// ── Bundle analyzer (opt-in: ANALYZE=true npm run build) ──────
const withBundleAnalyzer = (() => {
  try {
    if (process.env.ANALYZE === "true") {
      const analyzer = require("@next/bundle-analyzer")({
        enabled: true,
      });
      return analyzer;
    }
  } catch {
    // @next/bundle-analyzer not installed — skip
  }
  return (config: NextConfig) => config;
})();

export default withBundleAnalyzer(nextConfig);
