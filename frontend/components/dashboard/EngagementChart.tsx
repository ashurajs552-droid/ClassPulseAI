"use client";

import { motion } from "framer-motion";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

interface Props {
  data: { time: string; avg: number; high: number; low: number }[];
}

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number; color: string; name: string }[]; label?: string }) {
  if (!active || !payload) return null;
  return (
    <div className="glass p-3 text-xs !border-white/10">
      <p className="text-[#94a3b8] mb-1.5">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-[#94a3b8]">{p.name}:</span>
          <span className="text-white font-medium">{p.value.toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

export default function EngagementChart({ data }: Props) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Live Engagement</h3>
          <p className="text-[10px] text-[#64748b] mt-0.5">Real-time class engagement • Updates every 2s</p>
        </div>
        <div className="flex gap-3 text-[10px]">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#6366f1]" /> Average</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#10b981]" /> Highest</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#ef4444]" /> Lowest</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#475569" }} axisLine={false} tickLine={false} interval="preserveEnd" />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#475569" }} axisLine={false} tickLine={false} />
          <Tooltip content={<CustomTooltip />} />
          <Line type="monotone" dataKey="avg" name="Average" stroke="#6366f1" strokeWidth={2.5} dot={false} activeDot={{ r: 4, fill: "#6366f1" }} />
          <Line type="monotone" dataKey="high" name="Highest" stroke="#10b981" strokeWidth={1.5} dot={false} strokeDasharray="4 4" />
          <Line type="monotone" dataKey="low" name="Lowest" stroke="#ef4444" strokeWidth={1.5} dot={false} strokeDasharray="4 4" />
        </LineChart>
      </ResponsiveContainer>
    </motion.div>
  );
}
