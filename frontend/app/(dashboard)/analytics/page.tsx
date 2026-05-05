"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { AreaChart, Area, BarChart, Bar, PieChart, Pie, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid } from "recharts";
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
  const [range, setRange] = useState<"7d" | "30d" | "90d">("7d");
  const [loading, setLoading] = useState(true);
  const [hasData, setHasData] = useState(false);

  const [engagementData, setEngagementData] = useState<any[]>([]);
  const [emotionData, setEmotionData] = useState<any[]>([]);
  const [phoneData, setPhoneData] = useState<any[]>([]);

  useEffect(() => {
    fetchAnalytics();
  }, [range]);

  const fetchAnalytics = async () => {
    setLoading(true);
    const days = parseInt(range);
    const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

    try {
      const [engagementRes, emotionsRes, phonesRes] = await Promise.all([
        supabase.from('engagement_scores').select('score, timestamp').gte('timestamp', since).order('timestamp'),
        supabase.from('emotion_logs').select('emotion, timestamp').gte('timestamp', since),
        supabase.from('phone_detections').select('detected_at').gte('detected_at', since)
      ]);

      const rawEngagement = engagementRes.data || [];
      const rawEmotions = emotionsRes.data || [];
      const rawPhones = phonesRes.data || [];

      setHasData(rawEngagement.length > 0 || rawEmotions.length > 0 || rawPhones.length > 0);

      // Process Engagement Data (group by date)
      const engByDate: Record<string, number[]> = {};
      rawEngagement.forEach(d => {
        const date = new Date(d.timestamp).toLocaleDateString();
        if (!engByDate[date]) engByDate[date] = [];
        engByDate[date].push(d.score);
      });
      const processedEng = Object.entries(engByDate).map(([date, scores]) => ({
        date,
        score: scores.reduce((a, b) => a + b, 0) / scores.length
      }));
      setEngagementData(processedEng);

      // Process Emotion Data
      const emoCounts: Record<string, number> = {};
      rawEmotions.forEach(d => {
        emoCounts[d.emotion] = (emoCounts[d.emotion] || 0) + 1;
      });
      const processedEmo = Object.entries(emoCounts).map(([name, value]) => ({
        name,
        value,
        color: emotionColor(name)
      }));
      setEmotionData(processedEmo);

      // Process Phone Data
      const phoneByDate: Record<string, number> = {};
      rawPhones.forEach(d => {
        const date = new Date(d.detected_at).toLocaleDateString();
        phoneByDate[date] = (phoneByDate[date] || 0) + 1;
      });
      const processedPhones = Object.entries(phoneByDate).map(([date, count]) => ({
        date, count
      }));
      setPhoneData(processedPhones);

    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

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
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass p-5">
              <h3 className="text-sm font-semibold text-white mb-1">Engagement Trend</h3>
              <p className="text-[10px] text-[#64748b] mb-4">Daily average engagement score</p>
              <div className="h-[240px]">
                {engagementData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={engagementData}>
                      <defs>
                        <linearGradient id="colorScore" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<Tip />} />
                      <Area type="monotone" dataKey="score" stroke="#6366f1" fillOpacity={1} fill="url(#colorScore)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : <div className="h-full flex items-center justify-center text-sm text-[#475569]">No engagement data</div>}
              </div>
            </motion.div>

            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="glass p-5">
              <h3 className="text-sm font-semibold text-white mb-1">Emotion Patterns</h3>
              <p className="text-[10px] text-[#64748b] mb-4">Distribution of emotions</p>
              <div className="h-[240px] flex items-center justify-center">
                {emotionData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={emotionData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={2} strokeWidth={0}>
                        {emotionData.map((e, i) => <Cell key={i} fill={e.color} />)}
                      </Pie>
                      <Tooltip content={<Tip />} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : <div className="text-sm text-[#475569]">No emotion data</div>}
              </div>
              <div className="flex flex-wrap gap-3 justify-center mt-2">
                {emotionData.map((e, i) => (
                  <div key={i} className="flex items-center gap-1.5 text-xs text-[#94a3b8] capitalize">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ background: e.color }} />
                    {e.name}
                  </div>
                ))}
              </div>
            </motion.div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="glass p-5">
              <h3 className="text-sm font-semibold text-white mb-1">Phone Detection Frequency</h3>
              <p className="text-[10px] text-[#64748b] mb-4">Detected mobile phones by day</p>
              <div className="h-[200px]">
                {phoneData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={phoneData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<Tip />} />
                      <Bar dataKey="count" fill="#ef4444" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : <div className="h-full flex items-center justify-center text-sm text-[#475569]">No phone detections recorded</div>}
              </div>
            </motion.div>
          </div>
        </>
      )}
    </div>
  );
}
