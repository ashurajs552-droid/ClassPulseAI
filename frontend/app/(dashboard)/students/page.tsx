"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Plus, Edit2, Trash2, X, Upload, Users, Loader2 } from "lucide-react";
import { cn, engagementGrade } from "@/lib/utils";
import { toast } from "sonner";

interface Student {
  id: string; name: string; code: string; class: string; attendance: number; engagement: number; enrolled: string; photo: string | null; active: boolean;
}

const INITIAL: Student[] = [
  { id: "1", name: "Aanya Sharma", code: "STU-001", class: "CS 101", attendance: 96, engagement: 92, enrolled: "2025-08-15", photo: null, active: true },
  { id: "2", name: "James Chen", code: "STU-002", class: "CS 101", attendance: 94, engagement: 88, enrolled: "2025-08-15", photo: null, active: true },
  { id: "3", name: "Priya Patel", code: "STU-003", class: "CS 101", attendance: 89, engagement: 85, enrolled: "2025-08-15", photo: null, active: true },
  { id: "4", name: "Marcus Johnson", code: "STU-004", class: "CS 101", attendance: 91, engagement: 45, enrolled: "2025-08-15", photo: null, active: true },
  { id: "5", name: "Fatima Al-Hassan", code: "STU-005", class: "CS 101", attendance: 93, engagement: 52, enrolled: "2025-08-16", photo: null, active: true },
  { id: "6", name: "Liam O'Brien", code: "STU-006", class: "CS 101", attendance: 72, engagement: 28, enrolled: "2025-08-16", photo: null, active: true },
  { id: "7", name: "Yuki Tanaka", code: "STU-007", class: "CS 101", attendance: 98, engagement: 91, enrolled: "2025-08-16", photo: null, active: true },
  { id: "8", name: "Sofia Rodriguez", code: "STU-008", class: "CS 101", attendance: 95, engagement: 87, enrolled: "2025-08-17", photo: null, active: true },
  { id: "9", name: "David Kim", code: "STU-009", class: "CS 101", attendance: 90, engagement: 78, enrolled: "2025-08-17", photo: null, active: true },
  { id: "10", name: "Emma Williams", code: "STU-010", class: "CS 101", attendance: 85, engagement: 58, enrolled: "2025-08-17", photo: null, active: true },
];

export default function StudentsPage() {
  const [students, setStudents] = useState(INITIAL);
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [editStudent, setEditStudent] = useState<Student | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<"name" | "attendance" | "engagement">("name");
  const [form, setForm] = useState({ name: "", code: "", class: "CS 101" });

  const filtered = students
    .filter(s => s.name.toLowerCase().includes(search.toLowerCase()) || s.code.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortKey === "name") return a.name.localeCompare(b.name);
      return b[sortKey] - a[sortKey];
    });

  const handleAdd = () => {
    if (!form.name || !form.code) { toast.error("Name and Code are required"); return; }
    const newStudent: Student = { id: Date.now().toString(), name: form.name, code: form.code, class: form.class, attendance: 0, engagement: 0, enrolled: new Date().toISOString().split("T")[0], photo: null, active: true };
    setStudents(prev => [...prev, newStudent]);
    setForm({ name: "", code: "", class: "CS 101" });
    setShowAdd(false);
    toast.success("Student added successfully");
  };

  const handleDelete = (id: string) => {
    setStudents(prev => prev.filter(s => s.id !== id));
    setDeleteConfirm(null);
    toast.success("Student removed");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Students</h1>
          <p className="text-sm text-[#64748b] mt-0.5">Manage student enrollment and face data</p>
        </div>
        <motion.button whileTap={{ scale: 0.95 }} onClick={() => setShowAdd(true)} className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white font-medium text-sm">
          <Plus className="w-4 h-4" /> Add Student
        </motion.button>
      </div>

      {/* Search + Sort */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#475569]" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by name or code…" className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white placeholder:text-[#475569]" />
        </div>
        <div className="flex gap-1">
          {(["name", "attendance", "engagement"] as const).map(k => (
            <button key={k} onClick={() => setSortKey(k)} className={cn("px-3 py-2 rounded-lg text-xs font-medium capitalize transition", sortKey === k ? "bg-[#6366f1]/15 text-[#818cf8]" : "text-[#64748b] hover:text-white hover:bg-white/[0.04]")}>{k}</button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="glass overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#64748b] border-b border-white/[0.06] bg-white/[0.01]">
                <th className="text-left py-3 px-4 font-medium">Student</th>
                <th className="text-left py-3 px-4 font-medium">Code</th>
                <th className="text-left py-3 px-4 font-medium">Class</th>
                <th className="text-left py-3 px-4 font-medium">Attendance</th>
                <th className="text-left py-3 px-4 font-medium">Engagement</th>
                <th className="text-left py-3 px-4 font-medium">Enrolled</th>
                <th className="text-right py-3 px-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => {
                const g = engagementGrade(s.engagement);
                return (
                  <motion.tr key={s.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#6366f1]/20 to-[#8b5cf6]/20 flex items-center justify-center text-[10px] font-bold text-white border border-white/[0.06]">{s.name.split(" ").map(w => w[0]).join("")}</div>
                        <span className="text-white font-medium">{s.name}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-[#94a3b8] font-mono">{s.code}</td>
                    <td className="py-3 px-4 text-[#94a3b8]">{s.class}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-14 h-1.5 rounded-full bg-white/[0.06] overflow-hidden"><div className="h-full rounded-full bg-[#10b981]" style={{ width: `${s.attendance}%` }} /></div>
                        <span className="text-[#94a3b8]">{s.attendance}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{ color: g.color, background: g.color + "15" }}>{s.engagement}% — {g.grade}</span>
                    </td>
                    <td className="py-3 px-4 text-[#94a3b8]">{s.enrolled}</td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => setEditStudent(s)} className="w-7 h-7 rounded-lg flex items-center justify-center text-[#64748b] hover:text-[#6366f1] hover:bg-[#6366f1]/10 transition"><Edit2 className="w-3.5 h-3.5" /></button>
                        <button onClick={() => setDeleteConfirm(s.id)} className="w-7 h-7 rounded-lg flex items-center justify-center text-[#64748b] hover:text-[#ef4444] hover:bg-[#ef4444]/10 transition"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <div className="text-center py-12">
            <Users className="w-10 h-10 text-[#1e293b] mx-auto mb-3" />
            <p className="text-sm text-[#475569]">No students found</p>
          </div>
        )}
      </div>

      {/* Add Modal */}
      <AnimatePresence>
        {showAdd && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setShowAdd(false)}>
            <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} exit={{ scale: 0.9 }} onClick={e => e.stopPropagation()} className="glass-strong w-full max-w-md p-6">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-lg font-semibold text-white">Add Student</h3>
                <button onClick={() => setShowAdd(false)} className="text-[#64748b] hover:text-white"><X className="w-5 h-5" /></button>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">Full Name</label>
                  <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="John Doe" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white placeholder:text-[#475569]" />
                </div>
                <div>
                  <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">Student Code</label>
                  <input value={form.code} onChange={e => setForm({ ...form, code: e.target.value })} placeholder="STU-011" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white placeholder:text-[#475569]" />
                </div>
                <div>
                  <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">Photo (Face Enrollment)</label>
                  <div className="border-2 border-dashed border-white/[0.08] rounded-xl p-6 text-center hover:border-[#6366f1]/30 transition cursor-pointer">
                    <Upload className="w-8 h-8 text-[#475569] mx-auto mb-2" />
                    <p className="text-xs text-[#475569]">Drag & drop or click to upload</p>
                    <p className="text-[10px] text-[#334155] mt-1">Face encoding auto-generated via AI</p>
                  </div>
                </div>
                <button onClick={handleAdd} className="w-full py-2.5 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white font-medium text-sm">Add Student</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Delete Confirm */}
      <AnimatePresence>
        {deleteConfirm && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setDeleteConfirm(null)}>
            <motion.div initial={{ scale: 0.9 }} animate={{ scale: 1 }} exit={{ scale: 0.9 }} onClick={e => e.stopPropagation()} className="glass-strong w-full max-w-sm p-6 text-center">
              <div className="w-12 h-12 rounded-full bg-[#ef4444]/10 flex items-center justify-center mx-auto mb-4"><Trash2 className="w-6 h-6 text-[#ef4444]" /></div>
              <h3 className="text-lg font-semibold text-white mb-2">Delete Student?</h3>
              <p className="text-sm text-[#64748b] mb-6">This action cannot be undone. The student's face data and attendance records will be preserved.</p>
              <div className="flex gap-3">
                <button onClick={() => setDeleteConfirm(null)} className="flex-1 py-2.5 rounded-xl bg-white/[0.04] text-sm text-[#94a3b8] hover:text-white transition">Cancel</button>
                <button onClick={() => handleDelete(deleteConfirm)} className="flex-1 py-2.5 rounded-xl bg-[#ef4444]/15 text-[#ef4444] text-sm font-medium hover:bg-[#ef4444]/25 transition">Delete</button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
