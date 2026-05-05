"use client";

import { useEffect, useRef, useState } from "react";
import { useWebSocket } from "@/lib/websocket";
import { Activity, Clock, Cpu } from "lucide-react";
import { cn } from "@/lib/utils";
import DetectionOverlay from "./DetectionOverlay";

export default function VideoStream() {
  const { isConnected, lastFrame, metrics } = useWebSocket();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  // Handle canvas rendering from base64 frames
  useEffect(() => {
    if (!lastFrame || !canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    const img = new Image();
    img.onload = () => {
      // requestAnimationFrame for smoother rendering
      requestAnimationFrame(() => {
        if (canvas.width !== img.width || canvas.height !== img.height) {
          canvas.width = img.width;
          canvas.height = img.height;
        }
        ctx.drawImage(img, 0, 0);
      });
    };
    img.src = `data:image/jpeg;base64,${lastFrame.frame_b64}`;
  }, [lastFrame]);

  // Track container dimensions for the SVG overlay
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: containerRef.current.offsetHeight,
        });
      }
    };
    
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  return (
    <div className="flex flex-col h-full bg-[#05050a] rounded-xl overflow-hidden border border-white/[0.06]">
      {/* Top status bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white/[0.02] border-b border-white/[0.06] z-10 relative">
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-2 h-2 rounded-full",
            isConnected ? "bg-[#10b981] shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-[#ef4444]"
          )} />
          <span className="text-xs font-medium text-white">
            {isConnected ? "LIVE STREAM" : "DISCONNECTED"}
          </span>
        </div>
        
        {isConnected && (
          <div className="flex gap-4">
            <div className="flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-[#6366f1]" />
              <span className="text-[10px] text-[#94a3b8]">FPS:</span>
              <span className="text-xs font-mono text-white">{metrics?.fps?.toFixed(1) || "0.0"}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-[#06b6d4]" />
              <span className="text-[10px] text-[#94a3b8]">Latency:</span>
              <span className="text-xs font-mono text-white">{metrics?.latency_ms?.toFixed(0) || "0"}ms</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5 text-[#10b981]" />
              <span className="text-[10px] text-[#94a3b8]">Avg Eng:</span>
              <span className="text-xs font-mono text-white">{metrics?.avg_engagement?.toFixed(1) || "0.0"}%</span>
            </div>
          </div>
        )}
      </div>

      {/* Video area */}
      <div 
        ref={containerRef} 
        className="relative flex-1 bg-black flex items-center justify-center overflow-hidden"
      >
        {!isConnected && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-[#475569] z-20">
            <Activity className="w-10 h-10 mb-3 opacity-50" />
            <p className="text-sm font-medium text-white">No active session</p>
            <p className="text-xs mt-1">Start a session to begin live monitoring</p>
          </div>
        )}
        
        <canvas 
          ref={canvasRef} 
          className="max-w-full max-h-full object-contain pointer-events-none"
        />

        {isConnected && dimensions.width > 0 && (
          <DetectionOverlay 
            width={dimensions.width} 
            height={dimensions.height} 
            videoWidth={canvasRef.current?.width || 1920}
            videoHeight={canvasRef.current?.height || 1080}
          />
        )}
      </div>
    </div>
  );
}
