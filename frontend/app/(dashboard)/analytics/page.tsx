"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { AreaChart, Area, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, Legend } from "recharts";
import { Calendar, BarChart3 } from "lucide-react";
import { emotionColor } from "@/lib/utils";

const RANGES = ["7d", "30d", "90d"] as const;

// Mock data generators
const engagementTrend = Array.from({ length: 30 }, (_, i) => ({
  date: `Apr ${i + 1}`,
  score: 55 + Math.random() * 35,
}));

const emotionByDay = Array.from({ length: 7 }, (_, i) => ({
  day: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i],
  attentive: 8 + Math.floor(Math.random() * 12),
  engaged: 5 + Math.floor(Math.random() * 10),
  confused: 2 + Math.floor(Math.random() * 6),
  distracted: 2 + Math.floor(Math.random() * 5),
  sleepy: 1 + Math.floor(Math.random() * 4),
}));

const topStudents = [
  { name: "Aanya S.", engagement: 94 },
  { name: "Yuki T.", engagement: 91 },
  { name: "James C.", engagement: 88 },
  { name: "Sofia R.", engagement: 87 },
  { name: "David K.", engagement: 85 },
].reverse();

const bottomStudents = [
  { name: "Liam O.", engagement: 28 },
  { name: "Marcus J.", engagement: 42 },
  { name: "Fatima A.", engagement: 48 },
  { name: "Priya P.", engagement: 55 },
  { name: "Emma W.", engagement: 58 },
];

const phoneTrend = Array.from({ length: 7 }, (_, i) => ({
  day: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i],
  count: Math.floor(Math.random() * 8),
}));

const hourlyData = Array.from({ length: 8 }, (_, h) => ({
  hour: `${9 + h}:00`,
  Mon: 40 + Math.random() * 50,
  Tue: 40 + Math.random() * 50,
  Wed: 40 + Math.random() * 50,
  Thu: 40 + Math.random() * 50,
  Fri: 40 + Math.random() * 50,
}));

const radarData = [
  { metric: "Engagement", classA: 80, classB: 65 },
  { metric: "Attendance", classA: 92, classB: 88 },
  { metric: "Attention", classA: 75, classB: 70 },
  { metric: "Participation", classA: 68, classB: 72 },
  { metric: "Posture", classA: 70, classB: 60 },
];

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

      {/* Row 1: Engagement Trend + Emotion Patterns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass p-5">
          <h3 className="text-sm font-semibold text-white mb-1">Engagement Trend</h3>
          <p className="text-[10px] text-[#64748b] mb-4">Daily average engagement score</p>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={engagementTrend} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="engGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#475569" }} axisLine={false} tickLine={false} interval={4} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: "#475569" }} axisLine={false} tickLine={false} />
              <Tooltip content={<Tip />} />
              <Area type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2} fill="url(#engGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass p-5">
          <h3 className="text-sm font-semibold text-white mb-1">Emotion Patterns</h3>
          <p className="text-[10px] text-[#64748b] mb-4">Stacked breakdown by day</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={emotionByDay} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#475569" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: "#475569" }} axisLine={false} tickLine={false} />
              <Tooltip content={<Tip />} />
              {["attentive", "engaged", "confused", "distracted", "sleepy"].map(e => (
                <Bar key={e} dataKey={e} stackId="a" fill={emotionColor(e)} radius={e === "sleepy" ? [3, 3, 0, 0] : [0, 0, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      {/* Row 2: Per-Student + Phone Detection */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass p-5">
          <h3 className="text-sm font-semibold text-white mb-1">Top & Bottom Performers</h3>
          <p className="text-[10px] text-[#64748b] mb-4">By average engagement</p>
          <div className="space-y-4">
            <div>
              <p className="text-[10px] text-[#10b981] font-medium mb-2 uppercase tracking-wider">Top 5</p>
              {topStudents.map((s, i) => (
                <div key={i} className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] text-[#64748b] w-20 text-right">{s.name}</span>
                  <div className="flex-1 h-5 bg-white/[0.03] rounded-full overflow-hidden relative">
                    <motion.div initial={{ width: 0 }} animate={{ width: `${s.engagement}%` }} transition={{ delay: 0.3 + i * 0.08, duration: 0.6 }} className="h-full rounded-full bg-gradient-to-r from-[#10b981] to-[#6366f1]" />
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-white font-medium">{s.engagement}%</span>
                  </div>
                </div>
              ))}
            </div>
            <div>
              <p className="text-[10px] text-[#ef4444] font-medium mb-2 uppercase tracking-wider">Bottom 5</p>
              {bottomStudents.map((s, i) => (
                <div key={i} className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] text-[#64748b] w-20 text-right">{s.name}</span>
                  <div className="flex-1 h-5 bg-white/[0.03] rounded-full overflow-hidden relative">
                    <motion.div initial={{ width: 0 }} animate={{ width: `${s.engagement}%` }} transition={{ delay: 0.5 + i * 0.08, duration: 0.6 }} className="h-full rounded-full bg-gradient-to-r from-[#ef4444] to-[#f59e0b]" />
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-white font-medium">{s.engagement}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass p-5">
          <h3 className="text-sm font-semibold text-white mb-1">Phone Detection Frequency</h3>
          <p className="text-[10px] text-[#64748b] mb-4">Detected mobile phones by day</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={phoneTrend} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="day" tick={{ fontSize: 9, fill: "#475569" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: "#475569" }} axisLine={false} tickLine={false} />
              <Tooltip content={<Tip />} />
              <Bar dataKey="count" fill="#ef4444" radius={[4, 4, 0, 0]}>
                {phoneTrend.map((_, i) => <Cell key={i} fill={`rgba(239,68,68,${0.4 + (phoneTrend[i]?.count || 0) / 10})`} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          {/* Radar chart */}
          <h3 className="text-sm font-semibold text-white mt-6 mb-1">Class Comparison</h3>
          <p className="text-[10px] text-[#64748b] mb-3">Multi-dimensional class performance</p>
          <ResponsiveContainer width="100%" height={200}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="rgba(255,255,255,0.06)" />
              <PolarAngleAxis dataKey="metric" tick={{ fontSize: 9, fill: "#94a3b8" }} />
              <PolarRadiusAxis tick={false} axisLine={false} />
              <Radar name="CS 101" dataKey="classA" stroke="#6366f1" fill="#6366f1" fillOpacity={0.15} strokeWidth={2} />
              <Radar name="CS 201" dataKey="classB" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.1} strokeWidth={2} strokeDasharray="4 4" />
            </RadarChart>
          </ResponsiveContainer>
        </motion.div>
      </div>

      {/* Hourly Heatmap */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="glass p-5">
        <h3 className="text-sm font-semibold text-white mb-1">Hourly Engagement Heatmap</h3>
        <p className="text-[10px] text-[#64748b] mb-4">Engagement patterns by hour and day</p>
        <div className="overflow-x-auto">
          <div className="grid grid-cols-[auto_repeat(5,1fr)] gap-1 min-w-[500px]">
            <div />
            {["Mon", "Tue", "Wed", "Thu", "Fri"].map(d => <div key={d} className="text-center text-[10px] text-[#64748b] py-1">{d}</div>)}
            {hourlyData.map((row) => (
              <>
                <div key={`h-${row.hour}`} className="text-[10px] text-[#64748b] py-2 pr-2 text-right">{row.hour}</div>
                {(["Mon", "Tue", "Wed", "Thu", "Fri"] as const).map(day => {
                  const val = row[day] as number;
                  const intensity = Math.round((val / 100) * 255);
                  return (
                    <div key={`${row.hour}-${day}`} className="rounded-lg py-3 text-center text-[10px] font-medium" style={{
                      background: `rgba(99,102,241,${val / 150})`,
                      color: val > 60 ? "#fff" : "#94a3b8",
                    }}>{val.toFixed(0)}</div>
                  );
                })}
              </>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
