"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { supabase } from "@/lib/supabase";
import KPICards from "@/components/dashboard/KPICards";
import EngagementChart from "@/components/dashboard/EngagementChart";
import EmotionDistribution from "@/components/dashboard/EmotionDistribution";
import AlertsFeed from "@/components/dashboard/AlertsFeed";
import { engagementGrade } from "@/lib/utils";
import { Activity, Clock, ChevronRight, Phone, Brain, Moon, Inbox } from "lucide-react";

export default function DashboardPage() {
  const [students, setStudents] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const [studentsRes, sessionsRes] = await Promise.all([
        supabase.from("students").select("id, full_name").eq("is_active", true),
        supabase.from("sessions").select("*").order("started_at", { ascending: false }).limit(10),
      ]);
      setStudents(studentsRes.data || []);
      setSessions(sessionsRes.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const totalStudents = students.length;
  const recentSessions = sessions;

  return (
    <div className="relative space-y-6">
      {/* BG Animation — floating orbs */}
      <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden">
        <motion.div animate={{ x: [0, 60, 0], y: [0, -40, 0] }} transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-[5%] left-[10%] w-[450px] h-[450px] rounded-full bg-[#6366f1]/[0.06] blur-[120px]" />
        <motion.div animate={{ x: [0, -50, 0], y: [0, 50, 0] }} transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
          className="absolute top-[35%] right-[5%] w-[350px] h-[350px] rounded-full bg-[#8b5cf6]/[0.05] blur-[100px]" />
        <motion.div animate={{ x: [0, 40, 0], y: [0, -60, 0] }} transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
          className="absolute bottom-[10%] left-[35%] w-[300px] h-[300px] rounded-full bg-[#06b6d4]/[0.04] blur-[100px]" />
        <div className="absolute inset-0" style={{ backgroundImage: "radial-gradient(rgba(99,102,241,0.05) 1px, transparent 1px)", backgroundSize: "32px 32px" }} />
      </div>

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-[#64748b] mt-1">Real-time classroom monitoring overview</p>
      </motion.div>

      {/* KPI Cards */}
      <KPICards
        totalStudents={totalStudents}
        attendanceRate={0}
        avgEngagement={0}
        alertsCount={0}
      />

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3"><EngagementChart data={[]} /></div>
        <div className="lg:col-span-2"><EmotionDistribution data={{}} /></div>
      </div>

      {/* Quick Stats + Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }} className="glass p-5">
            <h3 className="text-sm font-semibold text-white mb-4">Quick Stats</h3>
            <div className="space-y-3">
              {[
                { icon: Phone, label: "Phone Detections", value: "0", color: "#ef4444" },
                { icon: Brain, label: "Confused Students", value: "0", color: "#f59e0b" },
                { icon: Moon, label: "Sleepy Students", value: "0", color: "#8b5cf6" },
                { icon: Activity, label: "Processing FPS", value: "—", color: "#10b981" },
                { icon: Clock, label: "Avg Latency", value: "—", color: "#06b6d4" },
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
        <div className="lg:col-span-3"><AlertsFeed alerts={[]} /></div>
      </div>

      {/* Recent Sessions */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7 }} className="glass p-5">
        <h3 className="text-sm font-semibold text-white mb-4">Recent Sessions</h3>
        {recentSessions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#64748b] border-b border-white/[0.06]">
                  <th className="text-left py-2.5 font-medium">Date</th>
                  <th className="text-left py-2.5 font-medium">Class</th>
                  <th className="text-left py-2.5 font-medium">Students</th>
                  <th className="text-left py-2.5 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {recentSessions.map((s: any) => (
                  <tr key={s.id} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition">
                    <td className="py-3 text-[#94a3b8]">{new Date(s.started_at).toLocaleDateString()}</td>
                    <td className="py-3 text-white font-medium">{s.class_id || "—"}</td>
                    <td className="py-3 text-[#94a3b8]">{s.total_students || 0}</td>
                    <td className="py-3"><span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#10b981]/10 text-[#10b981] capitalize">{s.status || "completed"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8">
            <Inbox className="w-8 h-8 text-[#1e293b] mx-auto mb-2" />
            <p className="text-sm text-[#475569]">No sessions yet</p>
            <p className="text-xs text-[#334155] mt-1">Start a live session to see data here</p>
          </div>
        )}
      </motion.div>
    </div>
  );
}
