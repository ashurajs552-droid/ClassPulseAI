"use client";

import { motion } from "framer-motion";
import { useSimulatedData } from "@/lib/websocket";
import KPICards from "@/components/dashboard/KPICards";
import EngagementChart from "@/components/dashboard/EngagementChart";
import EmotionDistribution from "@/components/dashboard/EmotionDistribution";
import AlertsFeed from "@/components/dashboard/AlertsFeed";
import { engagementGrade } from "@/lib/utils";
import { Activity, Clock, ChevronRight, Phone, Brain, Moon } from "lucide-react";

export default function DashboardPage() {
  const data = useSimulatedData();

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-[#64748b] mt-1">Real-time classroom monitoring overview</p>
      </motion.div>

      {/* KPI Cards */}
      <KPICards
        totalStudents={data.totalStudents}
        attendanceRate={+(data.presentStudents / data.totalStudents * 100).toFixed(1)}
        avgEngagement={+data.avgEngagement.toFixed(1)}
        alertsCount={data.alertsCount}
      />

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3">
          <EngagementChart data={data.engagementHistory} />
        </div>
        <div className="lg:col-span-2">
          <EmotionDistribution data={data.emotions} />
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Quick Stats */}
        <div className="lg:col-span-2 space-y-4">
          {/* Mini stats */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }} className="glass p-5">
            <h3 className="text-sm font-semibold text-white mb-4">Quick Stats</h3>
            <div className="space-y-3">
              {[
                { icon: Phone, label: "Phone Detections", value: data.phoneDetections.toString(), color: "#ef4444" },
                { icon: Brain, label: "Confused Students", value: (data.emotions.confused || 0).toString(), color: "#f59e0b" },
                { icon: Moon, label: "Sleepy Students", value: (data.emotions.sleepy || 0).toString(), color: "#8b5cf6" },
                { icon: Activity, label: "Processing FPS", value: data.fps.toString(), color: "#10b981" },
                { icon: Clock, label: "Avg Latency", value: data.latency + "ms", color: "#06b6d4" },
              ].map((s, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-white/[0.04] last:border-0">
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: s.color + "12" }}>
                      <s.icon className="w-3.5 h-3.5" style={{ color: s.color }} />
                    </div>
                    <span className="text-xs text-[#94a3b8]">{s.label}</span>
                  </div>
                  <span className="text-sm font-semibold text-white">{s.value}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Alerts Feed */}
        <div className="lg:col-span-3">
          <AlertsFeed alerts={data.alerts} />
        </div>
      </div>

      {/* Recent Sessions */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7 }} className="glass p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Recent Sessions</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#64748b] border-b border-white/[0.06]">
                <th className="text-left py-2.5 font-medium">Date</th>
                <th className="text-left py-2.5 font-medium">Class</th>
                <th className="text-left py-2.5 font-medium">Students</th>
                <th className="text-left py-2.5 font-medium">Engagement</th>
                <th className="text-left py-2.5 font-medium">Status</th>
                <th className="text-right py-2.5 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {data.recentSessions.map((s) => {
                const g = engagementGrade(s.engagement);
                return (
                  <tr key={s.id} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition">
                    <td className="py-3 text-[#94a3b8]">{s.date}</td>
                    <td className="py-3 text-white font-medium">{s.class_name}</td>
                    <td className="py-3 text-[#94a3b8]">{s.students}</td>
                    <td className="py-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{ color: g.color, background: g.color + "15" }}>
                        {s.engagement.toFixed(1)}% — {g.grade}
                      </span>
                    </td>
                    <td className="py-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#10b981]/10 text-[#10b981] capitalize">{s.status}</span>
                    </td>
                    <td className="py-3 text-right">
                      <button className="text-[#6366f1] hover:text-[#818cf8] transition">
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
