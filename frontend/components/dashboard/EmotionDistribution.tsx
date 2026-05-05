"use client";

import { motion } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { emotionColor, emotionEmoji } from "@/lib/utils";

interface Props {
  data: Record<string, number>;
}

const EMOTIONS = ["attentive", "engaged", "confused", "distracted", "sleepy"];

export default function EmotionDistribution({ data }: Props) {
  const chartData = EMOTIONS.map((e) => ({ name: e, value: data[e] || 0, color: emotionColor(e) }));
  const total = chartData.reduce((a, c) => a + c.value, 0) || 1;
  const dominant = chartData.reduce((a, c) => (c.value > a.value ? c : a), chartData[0]);

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="glass p-5">
      <h3 className="text-sm font-semibold text-white mb-1">Emotion Distribution</h3>
      <p className="text-[10px] text-[#64748b] mb-4">Current class mood breakdown</p>

      <div className="flex items-center gap-6">
        <div className="relative w-44 h-44 flex-shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={chartData} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={72} paddingAngle={3} strokeWidth={0}>
                {chartData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.[0]) return null;
                  const d = payload[0].payload;
                  return (
                    <div className="glass p-2.5 text-xs !border-white/10">
                      <span style={{ color: d.color }}>{emotionEmoji(d.name)} {d.name}</span>
                      <span className="text-white ml-2 font-medium">{d.value} ({((d.value / total) * 100).toFixed(0)}%)</span>
                    </div>
                  );
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          {/* Center label */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl">{emotionEmoji(dominant.name)}</span>
            <span className="text-[10px] text-[#94a3b8] capitalize mt-0.5">{dominant.name}</span>
          </div>
        </div>

        {/* Legend */}
        <div className="flex-1 space-y-2.5">
          {chartData.map((d) => (
            <div key={d.name} className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: d.color }} />
              <span className="text-xs text-[#94a3b8] capitalize flex-1">{d.name}</span>
              <span className="text-xs text-white font-medium">{d.value}</span>
              <span className="text-[10px] text-[#64748b] w-8 text-right">{((d.value / total) * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}
