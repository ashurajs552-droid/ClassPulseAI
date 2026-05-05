import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toFixed(0);
}

export function formatPct(v: number, d = 1): string {
  return v.toFixed(d) + "%";
}

export function emotionColor(e: string): string {
  return ({ attentive: "#10b981", engaged: "#6366f1", confused: "#f59e0b", distracted: "#f97316", sleepy: "#ef4444" })[e] || "#64748b";
}

export function emotionEmoji(e: string): string {
  return ({ attentive: "🎯", engaged: "✨", confused: "🤔", distracted: "😶", sleepy: "😴" })[e] || "❓";
}

export function severityColor(s: string): string {
  return ({ low: "#64748b", medium: "#f59e0b", high: "#f97316", critical: "#ef4444" })[s] || "#64748b";
}

export function engagementGrade(s: number): { grade: string; color: string } {
  if (s >= 85) return { grade: "Excellent", color: "#10b981" };
  if (s >= 70) return { grade: "Good", color: "#6366f1" };
  if (s >= 50) return { grade: "Average", color: "#f59e0b" };
  if (s >= 30) return { grade: "Low", color: "#f97316" };
  return { grade: "Critical", color: "#ef4444" };
}

export function timeAgo(d: string | Date): string {
  const s = Math.floor((Date.now() - new Date(d).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  return Math.floor(s / 86400) + "d ago";
}
