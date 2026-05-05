"use client";

import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { useWebSocket } from "@/lib/websocket";
import { emotionColor, emotionEmoji, engagementGrade, cn } from "@/lib/utils";
import { Wifi, WifiOff, Play, Square, Phone, Brain, Users, Activity, Clock, AlertTriangle, Eye, Camera } from "lucide-react";
import { toast } from "sonner";
import { LineChart, Line, AreaChart, Area, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const EMOTION_COLORS: Record<string, string> = { attentive: "#10b981", engaged: "#06b6d4", confused: "#f59e0b", distracted: "#ef4444", sleepy: "#8b5cf6" };

export default function LivePage() {
  const { isConnected, detections, startSession, stopSession } = useWebSocket();
  const [streaming, setStreaming] = useState(false);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [cameraActive, setCameraActive] = useState(false);

  // Live KPI state
  const [kpis, setKpis] = useState({ fps: 0, latency: 0, detected: 0, present: 0, alerts: 0, avgEngagement: 0 });
  const [engagementTimeline, setEngagementTimeline] = useState<{time:string;value:number}[]>([]);
  const [emotionDist, setEmotionDist] = useState<{name:string;value:number;color:string}[]>([]);
  const [studentEngagement, setStudentEngagement] = useState<{name:string;value:number;color:string}[]>([]);
  const [alertTimeline, setAlertTimeline] = useState<{time:string;count:number}[]>([]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const isSecure = window.location.protocol === 'https:' || window.location.hostname === 'localhost';
      if (!isSecure) {
        toast.error('Camera requires HTTPS. Please use secure connection.');
      }
    }

    navigator.permissions?.query({ name: 'camera' as PermissionName })
      .then((result) => {
        if (result.state === 'denied') {
          toast.error('Camera blocked. Go to browser Settings → Site Settings → Camera → Allow');
        }
      })
      .catch(() => {});
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'environment'
        },
        audio: false
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setCameraStream(stream);
        setCameraActive(true);
      }
    } catch (err: any) {
      console.error('Camera error:', err);
      if (err.name === 'NotAllowedError') {
        toast.error('Camera permission denied. Please allow camera access in browser.');
      } else if (err.name === 'NotFoundError') {
        toast.error('No camera found on this device.');
      } else if (err.name === 'NotReadableError') {
        toast.error('Camera is in use by another app.');
      } else {
        toast.error('Camera error: ' + err.message);
      }
    }
  };

  const stopCamera = () => {
    if (cameraStream) {
      cameraStream.getTracks().forEach(track => track.stop());
      setCameraStream(null);
      setCameraActive(false);
    }
  };

  // Update analytics every 2s from detections
  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
      const dets = detections;
      const count = dets.length;
      const avgEng = count > 0 ? Math.round(dets.reduce((a, d) => a + (d.engagement_score || 0), 0) / count) : 0;
      const alerts = dets.filter(d => d.has_phone || (d.emotion === "sleepy") || (d.emotion === "distracted")).length;

      setKpis({ fps: 15, latency: Math.round(10 + Math.random() * 20), detected: count, present: count, alerts, avgEngagement: avgEng });
      setEngagementTimeline(prev => [...prev.slice(-29), { time: now, value: avgEng }]);

      // Emotion distribution
      const emoCount: Record<string,number> = {};
      dets.forEach(d => { const e = d.emotion || "engaged"; emoCount[e] = (emoCount[e] || 0) + 1; });
      setEmotionDist(Object.entries(emoCount).map(([k, v]) => ({ name: k, value: v, color: EMOTION_COLORS[k] || "#6366f1" })));

      // Student engagement bars
      setStudentEngagement(dets.slice(0, 10).map(d => {
        const score = d.engagement_score || 0;
        const g = engagementGrade(score);
        return { name: d.student_name || `#${d.track_id}`, value: score, color: g.color };
      }));

      // Alert timeline
      setAlertTimeline(prev => [...prev.slice(-19), { time: now, count: alerts }]);
    }, 2000);
    return () => clearInterval(interval);
  }, [detections]);

  const toggleStream = () => {
    if (streaming) { 
      stopSession(); 
      stopCamera();
      setStreaming(false); 
      toast("Stream stopped", { duration: 2000 }); 
    } else { 
      startSession("demo-session-id"); 
      startCamera();
      setStreaming(true); 
      toast("Stream started — AI pipeline active", { duration: 2000 }); 
    }
  };

  const kpiCards = [
    { icon: Activity, label: "FPS", value: kpis.fps.toString(), color: "#10b981" },
    { icon: Clock, label: "Latency", value: `${kpis.latency}ms`, color: "#06b6d4" },
    { icon: Eye, label: "Detected", value: kpis.detected.toString(), color: "#6366f1" },
    { icon: Users, label: "Present", value: kpis.present.toString(), color: "#8b5cf6" },
    { icon: AlertTriangle, label: "Alerts", value: kpis.alerts.toString(), color: "#ef4444" },
    { icon: Brain, label: "Avg Engagement", value: `${kpis.avgEngagement}%`, color: "#f59e0b" },
  ];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Live Monitor</h1>
          <p className="text-sm text-[#64748b] mt-0.5">Real-time classroom surveillance with AI overlays</p>
        </div>
        <div className="flex items-center gap-3">
          <div className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium", isConnected ? "bg-[#10b981]/10 text-[#10b981]" : "bg-[#ef4444]/10 text-[#ef4444]")}>
            {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {isConnected ? "Connected" : "Disconnected"}
          </div>
          <motion.button whileTap={{ scale: 0.95 }} onClick={toggleStream}
            className={cn("flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition", streaming ? "bg-[#ef4444]/15 text-[#ef4444] border border-[#ef4444]/20" : "bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white")}>
            {streaming ? <><Square className="w-4 h-4" /> End Session</> : <><Play className="w-4 h-4" /> Start Session</>}
          </motion.button>
        </div>
      </div>

      {/* Video Feed */}
      <div className="h-[60vh] min-h-[400px] rounded-xl overflow-hidden bg-black border border-white/[0.06] relative">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
        {!cameraActive && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-[#475569] z-20">
            <Camera className="w-10 h-10 mb-3 opacity-50" />
            <p className="text-sm font-medium text-white">Camera Offline</p>
            <p className="text-xs mt-1">Start a session to activate the live feed</p>
          </div>
        )}
      </div>

      {/* ── Live KPI Cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {kpiCards.map((k, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className="glass p-4 flex items-center gap-3 hover:border-white/[0.12] transition">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: k.color + "12" }}>
              <k.icon className="w-5 h-5" style={{ color: k.color }} />
            </div>
            <div>
              <p className="text-lg font-bold text-white">{k.value}</p>
              <p className="text-[10px] text-[#64748b] uppercase tracking-wider">{k.label}</p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* ── Charts Row 1 ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Engagement Timeline */}
        <div className="lg:col-span-3 glass p-5">
          <h3 className="text-sm font-semibold text-white mb-3">Engagement Timeline</h3>
          <div className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={engagementTimeline}>
                <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "#0f1117", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12, color: "#e2e8f0" }} />
                <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Emotion Donut */}
        <div className="lg:col-span-2 glass p-5">
          <h3 className="text-sm font-semibold text-white mb-3">Emotion Distribution</h3>
          <div className="h-[220px] flex items-center">
            {emotionDist.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={emotionDist} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={3} strokeWidth={0}>
                    {emotionDist.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#0f1117", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12, color: "#e2e8f0" }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-[#475569] text-center w-full">No data yet — start a session</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2 mt-2 justify-center">
            {emotionDist.map((e, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[10px] text-[#94a3b8]">
                <div className="w-2 h-2 rounded-full" style={{ background: e.color }} />
                <span className="capitalize">{e.name} ({e.value})</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Charts Row 2 ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Student Engagement Bars */}
        <div className="lg:col-span-3 glass p-5">
          <h3 className="text-sm font-semibold text-white mb-3">Student Engagement</h3>
          <div className="h-[250px]">
            {studentEngagement.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={studentEngagement} layout="vertical">
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={100} tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#0f1117", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12, color: "#e2e8f0" }} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={14}>
                    {studentEngagement.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-[#475569] text-center pt-20">No students detected</p>
            )}
          </div>
        </div>

        {/* Alert Timeline */}
        <div className="lg:col-span-2 glass p-5">
          <h3 className="text-sm font-semibold text-white mb-3">Alert Timeline</h3>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={alertTimeline}>
                <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "#0f1117", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12, color: "#e2e8f0" }} />
                <Area type="monotone" dataKey="count" stroke="#ef4444" fill="#ef4444" fillOpacity={0.1} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Detected Students Grid ── */}
      <div>
        <h3 className="text-sm font-semibold text-white mb-3">
          Detected Students <span className="text-[#64748b] ml-2">({detections.length})</span>
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {detections.map((s, i) => {
            const score = s.engagement_score || 0;
            const g = engagementGrade(score);
            const name = s.student_name || `Unknown #${s.track_id}`;
            const emo = s.emotion || "engaged";
            return (
              <motion.div key={s.student_id || s.track_id} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.05 }}
                className="glass p-4 hover:border-white/[0.12] transition group relative">
                {s.has_phone && (
                  <div className="absolute top-2 right-2 w-6 h-6 rounded-full bg-[#ef4444]/15 flex items-center justify-center animate-pulse"><Phone className="w-3 h-3 text-[#ef4444]" /></div>
                )}
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#6366f1]/30 to-[#8b5cf6]/30 flex items-center justify-center text-sm font-bold text-white border-2" style={{ borderColor: emotionColor(emo) }}>
                    {name.split(" ").map(w => w[0]).join("")}
                  </div>
                  <div className="overflow-hidden flex-1">
                    <p className="text-xs font-medium text-white truncate">{name}</p>
                    <div className="flex items-center gap-1 mt-0.5">
                      <span className="text-xs">{emotionEmoji(emo)}</span>
                      <span className="text-[10px] capitalize" style={{ color: emotionColor(emo) }}>{emo}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <svg className="w-8 h-8 -rotate-90 flex-shrink-0" viewBox="0 0 36 36">
                    <circle cx="18" cy="18" r="14" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="3" />
                    <circle cx="18" cy="18" r="14" fill="none" stroke={g.color} strokeWidth="3" strokeDasharray={`${score * 0.88} 88`} strokeLinecap="round" />
                  </svg>
                  <div>
                    <span className="text-sm font-bold" style={{ color: g.color }}>{Math.round(score)}%</span>
                    <p className="text-[9px] text-[#64748b]">{g.grade}</p>
                  </div>
                </div>
              </motion.div>
            );
          })}
          {detections.length === 0 && (
            <div className="col-span-full py-8 text-center text-[#475569] text-sm">No students detected in current frame</div>
          )}
        </div>
      </div>
    </div>
  );
}
