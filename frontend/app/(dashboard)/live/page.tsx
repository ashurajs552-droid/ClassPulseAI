"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useWebSocket } from "@/lib/websocket";
import { emotionColor, emotionEmoji, engagementGrade, cn } from "@/lib/utils";
import { Wifi, WifiOff, Play, Square, Phone } from "lucide-react";
import { toast } from "sonner";
import VideoStream from "@/components/live/VideoStream";

const MOCK_STUDENTS = [
  { track_id: 1, name: "Aanya Sharma", emotion: "attentive", score: 92, hasPhone: false },
  { track_id: 2, name: "James Chen", emotion: "engaged", score: 88, hasPhone: false },
  { track_id: 3, name: "Priya Patel", emotion: "attentive", score: 85, hasPhone: false },
  { track_id: 4, name: "Marcus Johnson", emotion: "distracted", score: 45, hasPhone: true },
  { track_id: 5, name: "Fatima Al-Hassan", emotion: "confused", score: 52, hasPhone: false },
  { track_id: 6, name: "Liam O'Brien", emotion: "sleepy", score: 28, hasPhone: false },
  { track_id: 7, name: "Yuki Tanaka", emotion: "engaged", score: 91, hasPhone: false },
  { track_id: 8, name: "Sofia Rodriguez", emotion: "attentive", score: 87, hasPhone: false },
];

export default function LivePage() {
  const { isConnected, detections, startSession, stopSession } = useWebSocket();
  const [streaming, setStreaming] = useState(false);

  const toggleStream = () => {
    if (streaming) {
      stopSession();
      setStreaming(false);
      toast("Stream stopped", { duration: 2000 });
    } else {
      startSession("demo-session-id");
      setStreaming(true);
      toast("Stream started — AI pipeline active", { duration: 2000 });
    }
  };

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
          <motion.button
            whileTap={{ scale: 0.95 }}
            onClick={toggleStream}
            className={cn("flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-sm transition", streaming ? "bg-[#ef4444]/15 text-[#ef4444] border border-[#ef4444]/20 hover:bg-[#ef4444]/25" : "bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white hover:shadow-[0_0_30px_rgba(99,102,241,0.3)]")}
          >
            {streaming ? <><Square className="w-4 h-4" /> End Session</> : <><Play className="w-4 h-4" /> Start Session</>}
          </motion.button>
        </div>
      </div>

      {/* Video + Metrics */}
      <div className="h-[60vh] min-h-[400px]">
        <VideoStream />
      </div>

      {/* Student Grid */}
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
              <motion.div
                key={s.student_id || s.track_id}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.05 }}
                className="glass p-4 hover:border-white/[0.12] transition group relative"
              >
                {s.has_phone && (
                  <div className="absolute top-2 right-2 w-6 h-6 rounded-full bg-[#ef4444]/15 flex items-center justify-center animate-pulse">
                    <Phone className="w-3 h-3 text-[#ef4444]" />
                  </div>
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
                {/* Engagement ring */}
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
            <div className="col-span-full py-8 text-center text-[#475569] text-sm">
              No students detected in current frame
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
