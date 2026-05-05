"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Camera, SlidersHorizontal, Bell, User, Save, TestTube, Loader2 } from "lucide-react";
import { toast } from "sonner";

function Section({ title, icon: Icon, children }: { title: string; icon: typeof Camera; children: React.ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="glass p-6">
      <div className="flex items-center gap-2.5 mb-5">
        <div className="w-8 h-8 rounded-xl bg-[#6366f1]/10 flex items-center justify-center"><Icon className="w-4 h-4 text-[#818cf8]" /></div>
        <h3 className="text-sm font-semibold text-white">{title}</h3>
      </div>
      {children}
    </motion.div>
  );
}

function Slider({ label, value, onChange, min, max, step, unit }: { label: string; value: number; onChange: (v: number) => void; min: number; max: number; step: number; unit: string }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-white/[0.04] last:border-0">
      <label className="text-xs text-[#94a3b8]">{label}</label>
      <div className="flex items-center gap-3">
        <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(+e.target.value)} className="w-32 h-1 bg-white/[0.06] rounded-full appearance-none [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[#6366f1] [&::-webkit-slider-thumb]:cursor-pointer" />
        <span className="text-xs text-white font-mono w-14 text-right">{value}{unit}</span>
      </div>
    </div>
  );
}

function Toggle({ label, enabled, onChange }: { label: string; enabled: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-white/[0.04] last:border-0">
      <span className="text-xs text-[#94a3b8]">{label}</span>
      <button onClick={() => onChange(!enabled)} className={`w-9 h-5 rounded-full transition-colors ${enabled ? "bg-[#6366f1]" : "bg-white/[0.08]"} relative`}>
        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${enabled ? "left-[18px]" : "left-0.5"}`} />
      </button>
    </div>
  );
}

export default function SettingsPage() {
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const [camera, setCamera] = useState({ source: "0", resolution: "1920x1080", fps: 30 });
  const [thresholds, setThresholds] = useState({ face: 0.7, recognition: 0.68, emotion: 0.65, phone: 0.72 });
  const [notifs, setNotifs] = useState({ phone: true, engagement: true, sleeping: true, confusion: true, email: false, severity: "medium" });
  const [account, setAccount] = useState({ name: "Dr. Sarah Mitchell", school: "Westfield Academy" });

  const handleSave = async () => {
    setSaving(true);
    await new Promise(r => setTimeout(r, 1500));
    setSaving(false);
    toast.success("Settings saved successfully");
  };

  const handleTest = async () => {
    setTesting(true);
    await new Promise(r => setTimeout(r, 2000));
    setTesting(false);
    toast.success("Camera connection successful");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-sm text-[#64748b] mt-0.5">Configure cameras, AI models, and preferences</p>
        </div>
        <motion.button whileTap={{ scale: 0.95 }} onClick={handleSave} disabled={saving} className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white font-medium text-sm disabled:opacity-60">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? "Saving…" : "Save Changes"}
        </motion.button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Camera */}
        <Section title="Camera Configuration" icon={Camera}>
          <div className="space-y-1">
            <div className="flex items-center justify-between py-3 border-b border-white/[0.04]">
              <label className="text-xs text-[#94a3b8]">Source</label>
              <input value={camera.source} onChange={e => setCamera({ ...camera, source: e.target.value })} className="w-40 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-white text-right" />
            </div>
            <div className="flex items-center justify-between py-3 border-b border-white/[0.04]">
              <label className="text-xs text-[#94a3b8]">Resolution</label>
              <select value={camera.resolution} onChange={e => setCamera({ ...camera, resolution: e.target.value })} className="px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-white">
                <option value="1280x720" className="bg-[#0f1117]">720p</option>
                <option value="1920x1080" className="bg-[#0f1117]">1080p</option>
                <option value="3840x2160" className="bg-[#0f1117]">4K</option>
              </select>
            </div>
            <Slider label="FPS" value={camera.fps} onChange={v => setCamera({ ...camera, fps: v })} min={15} max={30} step={1} unit="" />
          </div>
          <button onClick={handleTest} disabled={testing} className="mt-4 flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.04] border border-white/[0.06] text-xs text-[#94a3b8] hover:text-white transition w-full justify-center disabled:opacity-50">
            {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TestTube className="w-3.5 h-3.5" />}
            {testing ? "Testing…" : "Test Connection"}
          </button>
        </Section>

        {/* Detection Thresholds */}
        <Section title="Detection Thresholds" icon={SlidersHorizontal}>
          <Slider label="Face Detection Confidence" value={thresholds.face} onChange={v => setThresholds({ ...thresholds, face: v })} min={0.5} max={0.95} step={0.05} unit="" />
          <Slider label="Recognition Similarity" value={thresholds.recognition} onChange={v => setThresholds({ ...thresholds, recognition: v })} min={0.5} max={0.9} step={0.02} unit="" />
          <Slider label="Emotion Confidence" value={thresholds.emotion} onChange={v => setThresholds({ ...thresholds, emotion: v })} min={0.4} max={0.9} step={0.05} unit="" />
          <Slider label="Phone Detection" value={thresholds.phone} onChange={v => setThresholds({ ...thresholds, phone: v })} min={0.5} max={0.95} step={0.01} unit="" />
        </Section>

        {/* Notifications */}
        <Section title="Notifications" icon={Bell}>
          <Toggle label="Phone Detection Alerts" enabled={notifs.phone} onChange={v => setNotifs({ ...notifs, phone: v })} />
          <Toggle label="Low Engagement Alerts" enabled={notifs.engagement} onChange={v => setNotifs({ ...notifs, engagement: v })} />
          <Toggle label="Mass Sleeping Alerts" enabled={notifs.sleeping} onChange={v => setNotifs({ ...notifs, sleeping: v })} />
          <Toggle label="High Confusion Alerts" enabled={notifs.confusion} onChange={v => setNotifs({ ...notifs, confusion: v })} />
          <Toggle label="Email Notifications" enabled={notifs.email} onChange={v => setNotifs({ ...notifs, email: v })} />
          <div className="flex items-center justify-between py-3">
            <span className="text-xs text-[#94a3b8]">Min Severity</span>
            <select value={notifs.severity} onChange={e => setNotifs({ ...notifs, severity: e.target.value })} className="px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-xs text-white">
              {["low", "medium", "high", "critical"].map(s => <option key={s} value={s} className="bg-[#0f1117] capitalize">{s}</option>)}
            </select>
          </div>
        </Section>

        {/* Account */}
        <Section title="Account" icon={User}>
          <div className="space-y-4">
            <div className="flex items-center gap-4 pb-4 border-b border-white/[0.04]">
              <div className="w-14 h-14 rounded-full bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center text-xl font-bold text-white">SM</div>
              <div>
                <p className="text-sm font-medium text-white">{account.name}</p>
                <button className="text-[10px] text-[#6366f1] hover:text-[#818cf8] transition mt-0.5">Change avatar</button>
              </div>
            </div>
            <div>
              <label className="block text-xs text-[#94a3b8] mb-1.5">Display Name</label>
              <input value={account.name} onChange={e => setAccount({ ...account, name: e.target.value })} className="w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white" />
            </div>
            <div>
              <label className="block text-xs text-[#94a3b8] mb-1.5">School Name</label>
              <input value={account.school} onChange={e => setAccount({ ...account, school: e.target.value })} className="w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white" />
            </div>
            <div>
              <label className="block text-xs text-[#94a3b8] mb-1.5">Password</label>
              <input type="password" placeholder="••••••••" className="w-full px-3 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-sm text-white placeholder:text-[#475569]" />
            </div>
          </div>
        </Section>
      </div>
    </div>
  );
}
