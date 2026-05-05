import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "ClassPulse AI — Intelligent Classroom Monitoring",
  description: "AI-powered real-time classroom monitoring with face recognition, emotion detection, engagement scoring, and automated reporting.",
  keywords: ["classroom monitoring", "AI", "face recognition", "engagement", "education technology"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet" />
      </head>
      <body style={{ fontFamily: "'Inter', system-ui, sans-serif" }}>
        {children}
        <Toaster
          position="top-right"
          toastOptions={{
            style: { background: "#0f1117", border: "1px solid rgba(255,255,255,0.08)", color: "#e2e8f0" },
          }}
          richColors
        />
      </body>
    </html>
  );
}
