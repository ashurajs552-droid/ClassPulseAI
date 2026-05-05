"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { UserCheck, UserX, Clock, Users, Download, Search, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const SESSIONS = [
  { id: "s1", label: "CS 101 — May 4, 2026 (9:00 AM)" },
  { id: "s2", label: "CS 101 — May 2, 2026 (9:00 AM)" },
  { id: "s3", label: "CS 101 — Apr 30, 2026 (2:00 PM)" },
];

type AttStatus = "present" | "absent" | "late";
type AttMarker = "ai" | "manual";
interface AttStudent { id: string; name: string; code: string; status: AttStatus; time: string; confidence: number; markedBy: AttMarker; }

const STUDENTS: AttStudent[] = [
  { id: "1", name: "Aanya Sharma", code: "STU-001", status: "present", time: "09:02", confidence: 0.97, markedBy: "ai" },
  { id: "2", name: "James Chen", code: "STU-002", status: "present", time: "09:01", confidence: 0.95, markedBy: "ai" },
  { id: "3", name: "Priya Patel", code: "STU-003", status: "late", time: "09:15", confidence: 0.89, markedBy: "ai" },
  { id: "4", name: "Marcus Johnson", code: "STU-004", status: "present", time: "09:00", confidence: 0.98, markedBy: "ai" },
  { id: "5", name: "Fatima Al-Hassan", code: "STU-005", status: "present", time: "09:03", confidence: 0.92, markedBy: "ai" },
  { id: "6", name: "Liam O'Brien", code: "STU-006", status: "absent", time: "—", confidence: 0, markedBy: "ai" },
  { id: "7", name: "Yuki Tanaka", code: "STU-007", status: "present", time: "09:01", confidence: 0.96, markedBy: "ai" },
  { id: "8", name: "Sofia Rodriguez", code: "STU-008", status: "present", time: "09:04", confidence: 0.93, markedBy: "ai" },
  { id: "9", name: "David Kim", code: "STU-009", status: "present", time: "09:02", confidence: 0.94, markedBy: "ai" },
  { id: "10", name: "Emma Williams", code: "STU-010", status: "late", time: "09:18", confidence: 0.88, markedBy: "manual" },
];

const statusColors = { present: "#10b981", late: "#f59e0b", absent: "#ef4444" };

export default function AttendancePage() {
  const [selectedSession, setSelectedSession] = useState(SESSIONS[0].id);
  const [search, setSearch] = useState("");
  const [students, setStudents] = useState(STUDENTS);

  const present = students.filter(s => s.status === "present").length;
  const late = students.filter(s => s.status === "late").length;
  const absent = students.filter(s => s.status === "absent").length;
  const total = students.length;

  const filtered = students.filter(s => s.name.toLowerCase().includes(search.toLowerCase()) || s.code.toLowerCase().includes(search.toLowerCase()));

  const ringData = [
    { name: "Present", value: present, color: "#10b981" },
    { name: "Late", value: late, color: "#f59e0b" },
    { name: "Absent", value: absent, color: "#ef4444" },
  ];

  const handleOverride = (id: string) => {
    const cycle: Record<AttStatus, AttStatus> = { present: "late", late: "absent", absent: "present" };
    setStudents(prev => prev.map(s => {
      if (s.id !== id) return s;
      return { ...s, status: cycle[s.status], markedBy: "manual" as AttMarker };
    }));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Attendance</h1>
          <p className="text-sm text-[#64748b] mt-0.5">Track student presence and recognition</p>
        </div>
        <div className="flex items-center gap-3">
          <select value={selectedSession} onChange={e => setSelectedSession(e.target.value)} className="px-3 py-2 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-white">
            {SESSIONS.map(s => <option key={s.id} value={s.id} className="bg-[#0f1117]">{s.label}</option>)}
          </select>
          <button className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-[#94a3b8] hover:text-white hover:border-white/[0.15] transition">
            <Download className="w-4 h-4" /> Export
          </button>
        </div>
      </div>

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
              <span className="text-xl font-bold text-white">{((present + late) / total * 100).toFixed(0)}%</span>
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
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[#64748b] border-b border-white/[0.06]">
                  <th className="text-left py-2.5 font-medium">Student</th>
                  <th className="text-left py-2.5 font-medium">ID</th>
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
                        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#6366f1]/20 to-[#8b5cf6]/20 flex items-center justify-center text-[10px] font-bold text-white">{s.name.split(" ").map(w => w[0]).join("")}</div>
                        <span className="text-white font-medium">{s.name}</span>
                      </div>
                    </td>
                    <td className="py-3 text-[#94a3b8] font-mono">{s.code}</td>
                    <td className="py-3">
                      <button onClick={() => handleOverride(s.id)} className="px-2 py-0.5 rounded-full text-[10px] font-medium capitalize cursor-pointer hover:ring-1 hover:ring-white/20 transition" style={{ color: statusColors[s.status], background: statusColors[s.status] + "15" }}>
                        {s.status}
                      </button>
                    </td>
                    <td className="py-3 text-[#94a3b8]">{s.time}</td>
                    <td className="py-3">
                      {s.confidence > 0 ? (
                        <div className="flex items-center gap-1.5">
                          <div className="w-16 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                            <div className="h-full rounded-full bg-[#6366f1]" style={{ width: `${s.confidence * 100}%` }} />
                          </div>
                          <span className="text-[#94a3b8]">{(s.confidence * 100).toFixed(0)}%</span>
                        </div>
                      ) : <span className="text-[#475569]">—</span>}
                    </td>
                    <td className="py-3">
                      <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-medium uppercase", s.markedBy === "ai" ? "text-[#06b6d4] bg-[#06b6d4]/10" : "text-[#f59e0b] bg-[#f59e0b]/10")}>{s.markedBy}</span>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
