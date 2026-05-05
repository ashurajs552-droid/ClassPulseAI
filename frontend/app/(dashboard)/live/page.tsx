"use client";

import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { emotionColor, emotionEmoji, engagementGrade, cn } from "@/lib/utils";
import { Wifi, WifiOff, Play, Square, Phone, Brain, Users, Activity, Clock, AlertTriangle, Eye, Camera, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { LineChart, Line, AreaChart, Area, PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { aiEngine } from "@/lib/ai-engine";
import { supabase } from "@/lib/supabase";

const EMOTION_COLORS: Record<string, string> = { attentive: "#10b981", engaged: "#06b6d4", confused: "#f59e0b", distracted: "#ef4444", sleepy: "#8b5cf6" };
const PROCESS_FPS = 30;
const PROCESS_INTERVAL = 1000 / PROCESS_FPS;

export default function LivePage() {
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  const [isSessionActive, setIsSessionActive] = useState(false);
  const [currentSession, setCurrentSession] = useState<any>(null);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);

  // Live KPI state
  const [fps, setFps] = useState(0);
  const [latency, setLatency] = useState(0);
  const [detectedCount, setDetectedCount] = useState(0);
  const [phoneCount, setPhoneCount] = useState(0);
  const [avgEngagement, setAvgEngagement] = useState(0);
  const [sleepyCount, setSleepyCount] = useState(0);
  const [confusedCount, setConfusedCount] = useState(0);
  const [emotionData, setEmotionData] = useState<Record<string, number>>({});
  
  const [engagementHistory, setEngagementHistory] = useState<{time:string;value:number}[]>([]);
  const [alertTimeline, setAlertTimeline] = useState<{time:string;count:number}[]>([]);
  const [currentDetections, setCurrentDetections] = useState<any[]>([]);

  // Refs for AI loop
  const lastProcessTime = useRef(0);
  const animFrameRef = useRef(0);
  const sessionIdRef = useRef<string|null>(null);
  const dbSaveInterval = useRef<any>(null);
  const pendingData = useRef<any[]>([]);

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
      
    return () => {
      cancelAnimationFrame(animFrameRef.current);
      clearInterval(dbSaveInterval.current);
      if (cameraStream) {
        cameraStream.getTracks().forEach(t => t.stop());
      }
    };
  }, []);

  const drawOverlays = (canvas: HTMLCanvasElement, video: HTMLVideoElement, detections: any[], phones: any[]) => {
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    detections.forEach(({ face, emotion, score }) => {
      const { x, y, width, height } = face.bbox;
      const color = EMOTION_COLORS[emotion] || '#6366f1';

      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.shadowColor = color;
      ctx.shadowBlur = 10;
      ctx.strokeRect(x, y, width, height);
      ctx.shadowBlur = 0;

      ctx.fillStyle = color + 'dd';
      ctx.fillRect(x, y - 32, Math.max(width, 140), 32);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 13px Inter, sans-serif';
      ctx.fillText(`${emotion} • ${score}%`, x + 6, y - 10);

      ctx.fillStyle = '#ffffff22';
      ctx.fillRect(x, y + height + 2, width, 5);
      ctx.fillStyle = color;
      ctx.fillRect(x, y + height + 2, (width * score) / 100, 5);
    });

    phones.forEach((phone: any) => {
      const [px, py, pw, ph] = phone.bbox;
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 3;
      ctx.setLineDash([5, 5]);
      ctx.strokeRect(px, py, pw, ph);
      ctx.setLineDash([]);
      ctx.fillStyle = '#ef4444dd';
      ctx.fillRect(px, py - 28, 120, 28);
      ctx.fillStyle = 'white';
      ctx.font = 'bold 12px Inter';
      ctx.fillText('📱 PHONE DETECTED', px + 4, py - 8);
    });
  };

  const processFrame = async (timestamp: number) => {
    if (!sessionIdRef.current) return;
    
    const elapsed = timestamp - lastProcessTime.current;
    if (elapsed < PROCESS_INTERVAL) {
      animFrameRef.current = requestAnimationFrame(processFrame);
      return;
    }
    lastProcessTime.current = timestamp;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) {
      animFrameRef.current = requestAnimationFrame(processFrame);
      return;
    }

    const start = performance.now();

    try {
      const [faces, phones] = await Promise.all([
        aiEngine.detectFaces(video),
        aiEngine.detectPhones(video)
      ]);

      const detections = faces.map((face: any) => {
        const { emotion, confidence } = aiEngine.detectEmotion(face);
        const score = aiEngine.calculateEngagement(face, emotion);
        return { face, emotion, confidence, score };
      });

      drawOverlays(canvas, video, detections, phones);

      const avgScore = detections.length > 0
        ? Math.round(detections.reduce((s: number, d: any) => s + d.score, 0) / detections.length)
        : 0;

      const emotionCounts = detections.reduce((acc: any, d: any) => {
        acc[d.emotion] = (acc[d.emotion] || 0) + 1;
        return acc;
      }, {});

      setDetectedCount(faces.length);
      setPhoneCount(phones.length);
      setAvgEngagement(avgScore);
      setEmotionData(emotionCounts);
      setSleepyCount(emotionCounts['sleepy'] || 0);
      setConfusedCount(emotionCounts['confused'] || 0);
      setFps(Math.round(1000 / elapsed));
      setLatency(Math.round(performance.now() - start));
      setCurrentDetections(detections);

      pendingData.current.push({
        detections, phones, timestamp: Date.now()
      });

      const nowStr = new Date().toLocaleTimeString();
      setEngagementHistory(prev => [
        ...prev.slice(-29),
        { time: nowStr, value: avgScore }
      ]);
      
      const totalAlerts = phones.length + (emotionCounts['sleepy'] || 0) + (emotionCounts['distracted'] || 0);
      setAlertTimeline(prev => [...prev.slice(-19), { time: nowStr, count: totalAlerts }]);

    } catch (err) {
      console.error('Frame error:', err);
    }

    animFrameRef.current = requestAnimationFrame(processFrame);
  };

  useEffect(() => {
    if (!isSessionActive) return;
    
    dbSaveInterval.current = setInterval(async () => {
      if (!sessionIdRef.current || pendingData.current.length === 0) return;
      
      const batch = [...pendingData.current];
      pendingData.current = [];
      
      const latest = batch[batch.length - 1];
      if (!latest) return;

      try {
        if (latest.detections.length > 0) {
          await supabase.from('emotion_logs').insert(
            latest.detections.map((d: any) => ({
              session_id: sessionIdRef.current,
              emotion: d.emotion,
              confidence: d.confidence,
              timestamp: new Date().toISOString()
            }))
          );

          await supabase.from('engagement_scores').insert(
            latest.detections.map((d: any) => ({
              session_id: sessionIdRef.current,
              score: d.score,
              attention_level: d.score / 100,
              timestamp: new Date().toISOString()
            }))
          );
        }

        if (latest.phones.length > 0) {
          await supabase.from('phone_detections').insert(
            latest.phones.map((p: any) => ({
              session_id: sessionIdRef.current,
              confidence: p.score,
              bbox: p.bbox,
              detected_at: new Date().toISOString()
            }))
          );

          await supabase.from('alerts').insert({
            session_id: sessionIdRef.current,
            type: 'phone_detected',
            message: `${latest.phones.length} phone(s) detected`,
            severity: 'high'
          });

          toast.error(`📱 Phone detected!`, { duration: 3000 });
        }

        const sleepy = latest.detections.filter((d: any) => d.emotion === 'sleepy').length;
        if (sleepy >= 2) {
          await supabase.from('alerts').insert({
            session_id: sessionIdRef.current,
            type: 'mass_sleeping',
            message: `${sleepy} students appear sleepy`,
            severity: sleepy >= 5 ? 'critical' : 'high'
          });
          toast.warning(`😴 ${sleepy} students sleepy!`);
        }

        const confused = latest.detections.filter((d: any) => d.emotion === 'confused').length;
        if (confused >= 3) {
          await supabase.from('alerts').insert({
            session_id: sessionIdRef.current,
            type: 'high_confusion',
            message: `${confused} students confused`,
            severity: 'medium'
          });
          toast.warning(`😕 ${confused} students confused!`);
        }

      } catch (err) {
        console.error('DB save error:', err);
      }
    }, 10000);

    return () => clearInterval(dbSaveInterval.current);
  }, [isSessionActive]);

  const startSession = async () => {
    setLoading(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!aiEngine.isInitialized) {
        setLoadingMsg('Initializing AI models...');
        await aiEngine.initialize();
      }

      setLoadingMsg('Starting camera...');
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { 
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 30 }
        },
        audio: false
      });

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraStream(stream);
      }

      const { data: session } = await supabase
        .from('sessions')
        .insert({
          teacher_id: user?.id,
          title: 'Live Class Session',
          started_at: new Date().toISOString(),
          status: 'active'
        })
        .select()
        .single();

      if (session) {
        sessionIdRef.current = session.id;
        setCurrentSession(session);
        setIsSessionActive(true);
        setStreaming(true);
        animFrameRef.current = requestAnimationFrame(processFrame);
        toast.success('Session started! AI active at 30 FPS');
      }
    } catch (err: any) {
      toast.error('Failed to start: ' + err.message);
    } finally {
      setLoading(false);
      setLoadingMsg('');
    }
  };

  const endSession = async () => {
    cancelAnimationFrame(animFrameRef.current);
    clearInterval(dbSaveInterval.current);
    setIsSessionActive(false);
    setStreaming(false);

    if (cameraStream) {
      cameraStream.getTracks().forEach(t => t.stop());
      setCameraStream(null);
    }

    if (sessionIdRef.current) {
      await supabase.from('sessions')
        .update({
          ended_at: new Date().toISOString(),
          status: 'completed',
          avg_engagement_score: avgEngagement,
          total_students: detectedCount
        })
        .eq('id', sessionIdRef.current);
    }

    toast.success('Session ended and saved!');
    sessionIdRef.current = null;
    setCurrentSession(null);
  };

  const toggleStream = () => {
    if (streaming) endSession();
    else startSession();
  };

  const kpiCards = [
    { icon: Activity, label: "FPS", value: fps.toString(), color: "#10b981" },
    { icon: Clock, label: "Latency", value: `${latency}ms`, color: "#06b6d4" },
    { icon: Eye, label: "Detected", value: detectedCount.toString(), color: "#6366f1" },
    { icon: Users, label: "Present", value: detectedCount.toString(), color: "#8b5cf6" },
    { icon: AlertTriangle, label: "Alerts", value: (phoneCount + sleepyCount + confusedCount).toString(), color: "#ef4444" },
    { icon: Brain, label: "Avg Engagement", value: `${avgEngagement}%`, color: "#f59e0b" },
  ];

  const emotionChartData = Object.entries(emotionData).map(([name, value]) => ({
    name, value, color: EMOTION_COLORS[name] || "#6366f1"
  }));

  const studentEngagementData = currentDetections.slice(0, 10).map((d, i) => {
    const g = engagementGrade(d.score);
    return { name: `Student ${i+1}`, value: d.score, color: g.color };
  });

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Live Monitor</h1>
          <p className="text-sm text-[#64748b] mt-0.5">Real-time classroom surveillance with AI overlays</p>
        </div>
        <div className="flex items-center gap-3">
          <div className={cn("flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium", isSessionActive ? "bg-[#10b981]/10 text-[#10b981]" : "bg-[#ef4444]/10 text-[#ef4444]")}>
            {isSessionActive ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {isSessionActive ? "AI Active" : "Standby"}
          </div>
          <motion.button whileTap={{ scale: 0.95 }} onClick={toggleStream} disabled={loading}
            className={cn("flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition disabled:opacity-70", streaming ? "bg-[#ef4444]/15 text-[#ef4444] border border-[#ef4444]/20" : "bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white")}>
            {loading ? <><Loader2 className="w-4 h-4 animate-spin" /> {loadingMsg}</> : streaming ? <><Square className="w-4 h-4" /> End Session</> : <><Play className="w-4 h-4" /> Start Session</>}
          </motion.button>
        </div>
      </div>

      {/* Video Feed */}
      <div className="relative w-full aspect-video bg-black rounded-xl overflow-hidden border border-white/[0.06]">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover"
        />
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full"
          style={{ pointerEvents: 'none' }}
        />
        {!streaming && !loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-[#475569] z-20 bg-black/80">
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
        <div className="lg:col-span-3 glass p-5">
          <h3 className="text-sm font-semibold text-white mb-3">Engagement Timeline</h3>
          <div className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={engagementHistory}>
                <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "#0f1117", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12, color: "#e2e8f0" }} />
                <Line type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-2 glass p-5">
          <h3 className="text-sm font-semibold text-white mb-3">Emotion Distribution</h3>
          <div className="h-[220px] flex items-center">
            {emotionChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={emotionChartData} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={75} paddingAngle={3} strokeWidth={0}>
                    {emotionChartData.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#0f1117", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12, color: "#e2e8f0" }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-[#475569] text-center w-full">No data yet — start a session</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2 mt-2 justify-center">
            {emotionChartData.map((e, i) => (
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
        <div className="lg:col-span-3 glass p-5">
          <h3 className="text-sm font-semibold text-white mb-3">Student Engagement</h3>
          <div className="h-[250px]">
            {studentEngagementData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={studentEngagementData} layout="vertical">
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={100} tick={{ fill: "#94a3b8", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: "#0f1117", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12, color: "#e2e8f0" }} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={14}>
                    {studentEngagementData.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-[#475569] text-center pt-20">No students detected</p>
            )}
          </div>
        </div>

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
      
    </div>
  );
}
