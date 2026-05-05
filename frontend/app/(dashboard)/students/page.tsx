"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Plus, Edit2, Trash2, X, Upload, Users, Loader2, Camera, Check } from "lucide-react";
import { cn, engagementGrade } from "@/lib/utils";
import { supabase } from "@/lib/supabase";
import { toast } from "sonner";

const SEMESTERS = ["1st Sem","2nd Sem","3rd Sem","4th Sem","5th Sem","6th Sem","7th Sem","8th Sem"];
const DEPARTMENTS = ["CSE","ISE","ECE","EEE","ME","CE","AIML","DS"];
const GENDERS = ["Male","Female","Other"];

interface Student {
  id: string; full_name: string; usn: string; phone_number: string;
  semester: string; department: string; gender: string;
  photo_url: string | null; is_active: boolean;
  attendance_pct?: number; engagement_avg?: number;
}

const emptyForm = { full_name:"", usn:"", phone_number:"", semester:"1st Sem", department:"CSE", gender:"Male" };

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<string|null>(null);
  const [sortKey, setSortKey] = useState<"full_name"|"attendance_pct"|"engagement_avg">("full_name");
  const [form, setForm] = useState(emptyForm);
  const [photo, setPhoto] = useState<string|null>(null);
  const [photoFile, setPhotoFile] = useState<File|null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [errors, setErrors] = useState<Record<string,string>>({});
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const streamRef = useRef<MediaStream|null>(null);

  // Load students from Supabase
  useEffect(() => {
    fetchStudents();
  }, []);

  const fetchStudents = async () => {
    setLoading(true);
    try {
      const { data, error } = await supabase
        .from("students")
        .select("id, full_name, usn, phone_number, semester, department, gender, photo_url, is_active")
        .eq("is_active", true)
        .order("full_name");
      if (error) throw error;
      setStudents((data || []).map(s => ({ ...s, attendance_pct: 0, engagement_avg: 0 })));
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  // Validation
  const validate = (): boolean => {
    const errs: Record<string,string> = {};
    if (!form.full_name || form.full_name.length < 3 || !/^[a-zA-Z\s]+$/.test(form.full_name))
      errs.full_name = "Name must be letters only, min 3 chars";
    if (!form.usn || !/^[a-zA-Z0-9]+$/.test(form.usn))
      errs.usn = "USN must be alphanumeric";
    if (!form.phone_number || !/^[6-9]\d{9}$/.test(form.phone_number))
      errs.phone_number = "Phone must be 10 digits starting with 6-9";
    if (!photo) errs.photo = "Please capture or upload a face photo";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // Camera
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: 640, height: 480 } });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play(); }
      setCameraOpen(true);
    } catch { toast.error("Camera access denied"); }
  };

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const ctx = canvasRef.current.getContext("2d");
    canvasRef.current.width = 640; canvasRef.current.height = 480;
    ctx?.drawImage(videoRef.current, 0, 0, 640, 480);
    const dataUrl = canvasRef.current.toDataURL("image/jpeg", 0.9);
    setPhoto(dataUrl);
    stopCamera();
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    setCameraOpen(false);
  };

  // File upload
  const handleFile = (file: File) => {
    if (file.size > 5 * 1024 * 1024) { toast.error("Photo must be under 5MB"); return; }
    if (!file.type.startsWith("image/")) { toast.error("File must be an image"); return; }
    setPhotoFile(file);
    const reader = new FileReader();
    reader.onload = () => setPhoto(reader.result as string);
    reader.readAsDataURL(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, []);

  // Submit
  const handleAdd = async () => {
    if (!validate()) return;
    setSubmitting(true);
    try {
      // Check USN uniqueness
      const { data: existing } = await supabase.from("students").select("id").eq("usn", form.usn.toUpperCase()).single();
      if (existing) { toast.error("USN already exists"); setSubmitting(false); return; }

      const { data, error } = await supabase.from("students").insert({
        full_name: form.full_name.trim(),
        usn: form.usn.toUpperCase(),
        phone_number: form.phone_number,
        semester: form.semester,
        department: form.department,
        gender: form.gender,
        is_active: true,
        enrollment_date: new Date().toISOString().split("T")[0],
      }).select().single();

      if (error) throw error;

      toast.success(`Student ${form.full_name} registered successfully!`);
      setForm(emptyForm); setPhoto(null); setPhotoFile(null); setShowAdd(false); setErrors({});
      fetchStudents();
    } catch (e: any) {
      toast.error(e.message || "Failed to add student");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await supabase.from("students").update({ is_active: false }).eq("id", id);
      setStudents(prev => prev.filter(s => s.id !== id));
      setDeleteConfirm(null);
      toast.success("Student removed");
    } catch { toast.error("Failed to delete"); }
  };

  const filtered = students
    .filter(s => s.full_name.toLowerCase().includes(search.toLowerCase()) || s.usn?.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortKey === "full_name") return a.full_name.localeCompare(b.full_name);
      return (b[sortKey] || 0) - (a[sortKey] || 0);
    });

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
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search by name or USN…" className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white placeholder:text-[#475569]" />
        </div>
        <div className="flex gap-1">
          {(["full_name","attendance_pct","engagement_avg"] as const).map(k => (
            <button key={k} onClick={() => setSortKey(k)} className={cn("px-3 py-2 rounded-lg text-xs font-medium capitalize transition", sortKey === k ? "bg-[#6366f1]/15 text-[#818cf8]" : "text-[#64748b] hover:text-white hover:bg-white/[0.04]")}>{k.replace("_"," ").replace("pct","%").replace("avg","")}</button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="glass overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16"><Loader2 className="w-6 h-6 text-[#6366f1] animate-spin" /></div>
        ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[#64748b] border-b border-white/[0.06] bg-white/[0.01]">
                <th className="text-left py-3 px-4 font-medium">Photo</th>
                <th className="text-left py-3 px-4 font-medium">Name</th>
                <th className="text-left py-3 px-4 font-medium">USN</th>
                <th className="text-left py-3 px-4 font-medium">Phone</th>
                <th className="text-left py-3 px-4 font-medium">Sem</th>
                <th className="text-left py-3 px-4 font-medium">Dept</th>
                <th className="text-left py-3 px-4 font-medium">Gender</th>
                <th className="text-left py-3 px-4 font-medium">Attendance%</th>
                <th className="text-left py-3 px-4 font-medium">Engagement</th>
                <th className="text-right py-3 px-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => {
                const g = engagementGrade(s.engagement_avg || 0);
                return (
                  <motion.tr key={s.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="border-b border-white/[0.03] hover:bg-white/[0.02] transition">
                    <td className="py-3 px-4">
                      <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#6366f1]/20 to-[#8b5cf6]/20 flex items-center justify-center text-[10px] font-bold text-white border border-white/[0.06] overflow-hidden">
                        {s.photo_url ? <img src={s.photo_url} alt="" className="w-full h-full object-cover" /> : s.full_name.split(" ").map(w => w[0]).join("")}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-white font-medium">{s.full_name}</td>
                    <td className="py-3 px-4 text-[#94a3b8] font-mono">{s.usn}</td>
                    <td className="py-3 px-4 text-[#94a3b8]">{s.phone_number}</td>
                    <td className="py-3 px-4 text-[#94a3b8]">{s.semester}</td>
                    <td className="py-3 px-4"><span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-[#6366f1]/10 text-[#818cf8]">{s.department}</span></td>
                    <td className="py-3 px-4 text-[#94a3b8]">{s.gender}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-14 h-1.5 rounded-full bg-white/[0.06] overflow-hidden"><div className="h-full rounded-full bg-[#10b981]" style={{ width: `${s.attendance_pct || 0}%` }} /></div>
                        <span className="text-[#94a3b8]">{s.attendance_pct || 0}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{ color: g.color, background: g.color + "15" }}>{s.engagement_avg || 0}%</span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => setDeleteConfirm(s.id)} className="w-7 h-7 rounded-lg flex items-center justify-center text-[#64748b] hover:text-[#ef4444] hover:bg-[#ef4444]/10 transition"><Trash2 className="w-3.5 h-3.5" /></button>
                      </div>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
        )}
        {!loading && filtered.length === 0 && (
          <div className="text-center py-12">
            <Users className="w-10 h-10 text-[#1e293b] mx-auto mb-3" />
            <p className="text-sm text-[#475569]">No students enrolled yet</p>
            <p className="text-xs text-[#334155] mt-1">Click "Add Student" to register your first student</p>
          </div>
        )}
      </div>

      {/* Add Modal */}
      <AnimatePresence>
        {showAdd && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => { setShowAdd(false); stopCamera(); }}>
            <motion.div initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.9, y: 20 }} onClick={e => e.stopPropagation()} className="glass-strong w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-lg font-semibold text-white">Register Student</h3>
                <button onClick={() => { setShowAdd(false); stopCamera(); }} className="text-[#64748b] hover:text-white"><X className="w-5 h-5" /></button>
              </div>

              <div className="space-y-4">
                {/* Full Name */}
                <div>
                  <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">Full Name <span className="text-[#ef4444]">*</span></label>
                  <input value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} placeholder="John Doe" className={cn("w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border text-sm text-white placeholder:text-[#475569]", errors.full_name ? "border-[#ef4444]/50" : "border-white/[0.06]")} />
                  {errors.full_name && <p className="text-[10px] text-[#ef4444] mt-1">{errors.full_name}</p>}
                </div>

                {/* USN */}
                <div>
                  <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">USN <span className="text-[#ef4444]">*</span></label>
                  <input value={form.usn} onChange={e => setForm({...form, usn: e.target.value.toUpperCase()})} placeholder="1RV22CS001" className={cn("w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border text-sm text-white placeholder:text-[#475569] font-mono uppercase", errors.usn ? "border-[#ef4444]/50" : "border-white/[0.06]")} />
                  {errors.usn && <p className="text-[10px] text-[#ef4444] mt-1">{errors.usn}</p>}
                </div>

                {/* Phone */}
                <div>
                  <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">Phone Number <span className="text-[#ef4444]">*</span></label>
                  <input type="tel" value={form.phone_number} onChange={e => { const v = e.target.value.replace(/\D/g,"").slice(0,10); setForm({...form, phone_number: v}); }} placeholder="9876543210" maxLength={10} className={cn("w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border text-sm text-white placeholder:text-[#475569]", errors.phone_number ? "border-[#ef4444]/50" : "border-white/[0.06]")} />
                  {errors.phone_number && <p className="text-[10px] text-[#ef4444] mt-1">{errors.phone_number}</p>}
                </div>

                {/* Semester + Department */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">Semester</label>
                    <select value={form.semester} onChange={e => setForm({...form, semester: e.target.value})} className="w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white">
                      {SEMESTERS.map(s => <option key={s} value={s} className="bg-[#0f1117]">{s}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">Department</label>
                    <select value={form.department} onChange={e => setForm({...form, department: e.target.value})} className="w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white">
                      {DEPARTMENTS.map(d => <option key={d} value={d} className="bg-[#0f1117]">{d}</option>)}
                    </select>
                  </div>
                </div>

                {/* Gender */}
                <div>
                  <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">Gender</label>
                  <div className="flex gap-3">
                    {GENDERS.map(g => (
                      <label key={g} className={cn("flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm cursor-pointer transition", form.gender === g ? "border-[#6366f1]/50 bg-[#6366f1]/10 text-white" : "border-white/[0.06] bg-white/[0.02] text-[#94a3b8] hover:border-white/[0.12]")}>
                        <div className={cn("w-4 h-4 rounded-full border-2 flex items-center justify-center", form.gender === g ? "border-[#6366f1]" : "border-[#475569]")}>
                          {form.gender === g && <div className="w-2 h-2 rounded-full bg-[#6366f1]" />}
                        </div>
                        {g}
                        <input type="radio" name="gender" value={g} checked={form.gender === g} onChange={() => setForm({...form, gender: g})} className="hidden" />
                      </label>
                    ))}
                  </div>
                </div>

                {/* Face Photo */}
                <div>
                  <label className="block text-xs text-[#94a3b8] mb-1.5 font-medium">Face Photo <span className="text-[#ef4444]">*</span></label>
                  {photo ? (
                    <div className="relative">
                      <img src={photo} alt="Captured" className="w-full h-48 object-cover rounded-xl border border-white/[0.08]" />
                      <button onClick={() => { setPhoto(null); setPhotoFile(null); }} className="absolute top-2 right-2 w-7 h-7 rounded-full bg-black/60 flex items-center justify-center text-white hover:bg-black/80"><X className="w-4 h-4" /></button>
                      <div className="absolute bottom-2 left-2 px-2 py-1 rounded-lg bg-[#10b981]/20 text-[#10b981] text-[10px] font-medium flex items-center gap-1"><Check className="w-3 h-3" /> Photo captured</div>
                    </div>
                  ) : cameraOpen ? (
                    <div className="relative">
                      <video ref={videoRef} autoPlay playsInline muted className="w-full h-48 object-cover rounded-xl border border-white/[0.08]" />
                      <button onClick={capturePhoto} className="absolute bottom-3 left-1/2 -translate-x-1/2 px-4 py-2 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white text-xs font-medium flex items-center gap-1.5"><Camera className="w-3.5 h-3.5" /> Capture</button>
                    </div>
                  ) : (
                    <div className="flex gap-3">
                      <button onClick={startCamera} className="flex-1 border-2 border-dashed border-white/[0.08] rounded-xl p-6 text-center hover:border-[#6366f1]/30 transition cursor-pointer">
                        <Camera className="w-8 h-8 text-[#475569] mx-auto mb-2" />
                        <p className="text-xs text-[#475569]">Use Webcam</p>
                      </button>
                      <div onClick={() => fileRef.current?.click()} onDragOver={e => e.preventDefault()} onDrop={handleDrop} className="flex-1 border-2 border-dashed border-white/[0.08] rounded-xl p-6 text-center hover:border-[#6366f1]/30 transition cursor-pointer">
                        <Upload className="w-8 h-8 text-[#475569] mx-auto mb-2" />
                        <p className="text-xs text-[#475569]">Drag & Drop</p>
                        <p className="text-[10px] text-[#334155] mt-1">Max 5MB</p>
                      </div>
                      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]); }} />
                    </div>
                  )}
                  {errors.photo && <p className="text-[10px] text-[#ef4444] mt-1">{errors.photo}</p>}
                </div>

                <canvas ref={canvasRef} className="hidden" />

                <button onClick={handleAdd} disabled={submitting} className="w-full py-2.5 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white font-medium text-sm disabled:opacity-50 flex items-center justify-center gap-2">
                  {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Registering…</> : "Register Student"}
                </button>
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
              <p className="text-sm text-[#64748b] mb-6">This will deactivate the student. Their records will be preserved.</p>
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
