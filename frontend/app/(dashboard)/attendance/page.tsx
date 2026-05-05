"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { UserCheck, UserX, Clock, Users, Download, Search, Inbox, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { supabase } from "@/lib/supabase";

export default function AttendancePage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [selectedSession, setSelectedSession] = useState<string>("");
  const [attendance, setAttendance] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSessions();
  }, []);

  useEffect(() => {
    if (selectedSession) fetchAttendance();
  }, [selectedSession]);

  const fetchSessions = async () => {
    try {
      const { data } = await supabase.from("sessions").select("id, started_at, classes(name)").order("started_at", { ascending: false });
      if (data && data.length > 0) {
        setSessions(data);
        setSelectedSession(data[0].id);
      } else {
        setLoading(false);
      }
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  const fetchAttendance = async () => {
    setLoading(true);
    try {
      const { data } = await supabase
        .from("attendance")
        .select("*, students(full_name, usn)")
        .eq("session_id", selectedSession);
      setAttendance(data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const present = attendance.filter(s => s.status === "present").length;
  const late = attendance.filter(s => s.status === "late").length;
  const absent = attendance.filter(s => s.status === "absent").length;
  const total = attendance.length;

  const filtered = attendance.filter(s => {
    const name = s.students?.full_name?.toLowerCase() || "";
    const usn = s.students?.usn?.toLowerCase() || "";
    const q = search.toLowerCase();
    return name.includes(q) || usn.includes(q);
  });

  const ringData = [
    { name: "Present", value: present, color: "#10b981" },
    { name: "Late", value: late, color: "#f59e0b" },
    { name: "Absent", value: absent, color: "#ef4444" },
  ];

  const handleOverride = async (id: string, currentStatus: string) => {
    const cycle: Record<string, string> = { present: "late", late: "absent", absent: "present" };
    const newStatus = cycle[currentStatus];
    
    // Optimistic update
    setAttendance(prev => prev.map(a => a.id === id ? { ...a, status: newStatus, marked_by: "manual" } : a));
    
    try {
      await supabase.from("attendance").update({ status: newStatus, marked_by: "manual" }).eq("id", id);
    } catch (e) {
      console.error(e);
      // Revert on failure
      fetchAttendance();
    }
  };

  const statusColors: Record<string, string> = { present: "#10b981", late: "#f59e0b", absent: "#ef4444" };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Attendance</h1>
          <p className="text-sm text-[#64748b] mt-0.5">Track student presence and recognition</p>
        </div>
        <div className="flex items-center gap-3">
          {sessions.length > 0 && (
            <select value={selectedSession} onChange={e => setSelectedSession(e.target.value)} className="px-3 py-2 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-white">
              {sessions.map(s => (
                <option key={s.id} value={s.id} className="bg-[#0f1117]">
                  {s.classes?.name || "Unknown"} — {new Date(s.started_at).toLocaleString()}
                </option>
              ))}
            </select>
          )}
          <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-[#94a3b8] hover:text-white hover:border-white/[0.15] transition">
            <Download className="w-4 h-4" /> Export
          </button>
        </div>
      </div>

      {sessions.length === 0 && !loading ? (
        <div className="text-center py-20 glass">
          <Inbox className="w-12 h-12 text-[#1e293b] mx-auto mb-4" />
          <p className="text-lg font-medium text-white">No sessions found</p>
          <p className="text-sm text-[#475569] mt-1">Start a live monitoring session to collect attendance.</p>
        </div>
      ) : (
        <>
          {/* Summary + Ring */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-1 glass p-6 flex items-center gap-6">
              <div className="relative w-32 h-32 flex-shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={ringData} dataKey="value" cx="50%" cy="50%" innerRadius={38} outerRadius={52} paddingAngle={4} strokeWidth={0}>
                      {ringData.map((e, i) => <Cell key={i} fill={e.color} />)}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-xl font-bold text-white">{total > 0 ? ((present + late) / total * 100).toFixed(0) : 0}%</span>
                  <span className="text-[9px] text-[#64748b]">Present</span>
                </div>
              </div>
              <div className="space-y-3">
                {[
                  { icon: UserCheck, label: "Present", value: present, color: "#10b981" },
                  { icon: Clock, label: "Late", value: late, color: "#f59e0b" },
                  { icon: UserX, label: "Absent", value: absent, color: "#ef4444" },
                  { icon: Users, label: "Total", value: total, color: "#6366f1" },
                ].map((s, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: s.color + "12" }}>
                      <s.icon className="w-3.5 h-3.5" style={{ color: s.color }} />
                    </div>
                    <span className="text-xs text-[#94a3b8] flex-1">{s.label}</span>
                    <span className="text-sm font-semibold text-white">{s.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Student Table */}
            <div className="lg:col-span-2 glass p-5">
              <div className="flex items-center gap-3 mb-4">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#475569]" />
                  <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search students…" className="w-full pl-9 pr-4 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white placeholder:text-[#475569]" />
                </div>
              </div>
              
              {loading ? (
                <div className="flex justify-center py-10"><Loader2 className="w-6 h-6 text-[#6366f1] animate-spin" /></div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-[#64748b] border-b border-white/[0.06]">
                        <th className="text-left py-2.5 font-medium">Student</th>
                        <th className="text-left py-2.5 font-medium">USN</th>
                        <th className="text-left py-2.5 font-medium">Status</th>
                        <th className="text-left py-2.5 font-medium">Time</th>
                        <th className="text-left py-2.5 font-medium">Confidence</th>
                        <th className="text-left py-2.5 font-medium">Marked By</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((s) => (
                        <motion.tr key={s.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition">
                          <td className="py-3">
                            <div className="flex items-center gap-2.5">
                              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#6366f1]/20 to-[#8b5cf6]/20 flex items-center justify-center text-[10px] font-bold text-white">{(s.students?.full_name || "?").substring(0,2).toUpperCase()}</div>
                              <span className="text-white font-medium">{s.students?.full_name || "Unknown"}</span>
                            </div>
                          </td>
                          <td className="py-3 text-[#94a3b8] font-mono">{s.students?.usn || "—"}</td>
                          <td className="py-3">
                            <button onClick={() => handleOverride(s.id, s.status)} className="px-2 py-0.5 rounded-full text-[10px] font-medium capitalize cursor-pointer hover:ring-1 hover:ring-white/20 transition" style={{ color: statusColors[s.status], background: statusColors[s.status] + "15" }}>
                              {s.status}
                            </button>
                          </td>
                          <td className="py-3 text-[#94a3b8]">{new Date(s.detected_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</td>
                          <td className="py-3">
                            {s.recognition_confidence > 0 ? (
                              <div className="flex items-center gap-1.5">
                                <div className="w-16 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                                  <div className="h-full rounded-full bg-[#6366f1]" style={{ width: `${s.recognition_confidence * 100}%` }} />
                                </div>
                                <span className="text-[#94a3b8]">{(s.recognition_confidence * 100).toFixed(0)}%</span>
                              </div>
                            ) : <span className="text-[#475569]">—</span>}
                          </td>
                          <td className="py-3">
                            <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-medium uppercase", s.marked_by === "ai" ? "text-[#06b6d4] bg-[#06b6d4]/10" : "text-[#f59e0b] bg-[#f59e0b]/10")}>{s.marked_by}</span>
                          </td>
                        </motion.tr>
                      ))}
                    </tbody>
                  </table>
                  
                  {filtered.length === 0 && (
                    <div className="text-center py-10 text-[#475569] text-sm">No attendance records found</div>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
