"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { AreaChart, Area, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import { Inbox, Loader2 } from "lucide-react";
import { emotionColor } from "@/lib/utils";
import { supabase } from "@/lib/supabase";

const RANGES = ["7d", "30d", "90d"] as const;

function Tip({ active, payload, label }: { active?: boolean; payload?: { value: number; color?: string; name?: string }[]; label?: string }) {
  if (!active || !payload) return null;
  return (
    <div className="glass p-2.5 text-xs !border-white/10">
      <p className="text-[#94a3b8] mb-1">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-1.5">
          {p.color && <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />}
          <span className="text-white font-medium">{typeof p.value === "number" ? p.value.toFixed(1) : p.value}{p.name && ` (${p.name})`}</span>
        </div>
      ))}
    </div>
  );
}

export default function AnalyticsPage() {
  const [range, setRange] = useState<"7d" | "30d" | "90d">("30d");
  const [loading, setLoading] = useState(true);
  const [hasData, setHasData] = useState(false);

  useEffect(() => {
    // Check if we have any sessions/analytics data
    const checkData = async () => {
      setLoading(true);
      try {
        const { count } = await supabase.from("sessions").select("*", { count: "exact", head: true });
        setHasData((count || 0) > 0);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    checkData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Analytics</h1>
          <p className="text-sm text-[#64748b] mt-0.5">Deep dive into classroom performance data</p>
        </div>
        <div className="flex items-center gap-2">
          {RANGES.map(r => (
            <button key={r} onClick={() => setRange(r)} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${range === r ? "bg-[#6366f1]/15 text-[#818cf8] border border-[#6366f1]/20" : "text-[#64748b] hover:text-white hover:bg-white/[0.04]"}`}>{r === "7d" ? "7 Days" : r === "30d" ? "30 Days" : "90 Days"}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 text-[#6366f1] animate-spin" /></div>
      ) : !hasData ? (
        <div className="text-center py-20 glass">
          <Inbox className="w-12 h-12 text-[#1e293b] mx-auto mb-4" />
          <p className="text-lg font-medium text-white">No analytics data yet</p>
          <p className="text-sm text-[#475569] mt-1">Start a live monitoring session to collect engagement metrics.</p>
        </div>
      ) : (
        <>
          {/* Row 1: Engagement Trend + Emotion Patterns */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass p-5">
              <h3 className="text-sm font-semibold text-white mb-1">Engagement Trend</h3>
              <p className="text-[10px] text-[#64748b] mb-4">Daily average engagement score</p>
              <div className="h-[240px] flex items-center justify-center text-sm text-[#475569]">
                Collecting data...
              </div>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass p-5">
              <h3 className="text-sm font-semibold text-white mb-1">Emotion Patterns</h3>
              <p className="text-[10px] text-[#64748b] mb-4">Stacked breakdown by day</p>
              <div className="h-[240px] flex items-center justify-center text-sm text-[#475569]">
                Collecting data...
              </div>
            </motion.div>
          </div>

          {/* Row 2: Per-Student + Phone Detection */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass p-5">
              <h3 className="text-sm font-semibold text-white mb-1">Top & Bottom Performers</h3>
              <p className="text-[10px] text-[#64748b] mb-4">By average engagement</p>
              <div className="h-[200px] flex items-center justify-center text-sm text-[#475569]">
                Not enough data yet.
              </div>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass p-5">
              <h3 className="text-sm font-semibold text-white mb-1">Phone Detection Frequency</h3>
              <p className="text-[10px] text-[#64748b] mb-4">Detected mobile phones by day</p>
              <div className="h-[200px] flex items-center justify-center text-sm text-[#475569]">
                Collecting data...
              </div>
            </motion.div>
          </div>

          {/* Hourly Heatmap */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="glass p-5">
            <h3 className="text-sm font-semibold text-white mb-1">Hourly Engagement Heatmap</h3>
            <p className="text-[10px] text-[#64748b] mb-4">Engagement patterns by hour and day</p>
            <div className="h-[200px] flex items-center justify-center text-sm text-[#475569]">
              Insufficient data for heatmap generation.
            </div>
          </motion.div>
        </>
      )}
    </div>
  );
}
