"use client";

import { useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useWebSocket } from "@/lib/websocket";
import { emotionColor } from "@/lib/utils";

interface DetectionOverlayProps {
  width: number;
  height: number;
  videoWidth: number;
  videoHeight: number;
}

export default function DetectionOverlay({ width, height, videoWidth, videoHeight }: DetectionOverlayProps) {
  const { detections } = useWebSocket();

  // Calculate scale to map video coordinates to DOM coordinates
  // Canvas object-fit: contain logic
  const scale = useMemo(() => {
    // Prevent division by zero
    if (videoWidth === 0 || videoHeight === 0) return { scaleX: 1, scaleY: 1, offsetX: 0, offsetY: 0 };
    
    const videoRatio = videoWidth / videoHeight;
    const containerRatio = width / height;
    
    let renderWidth = width;
    let renderHeight = height;
    let offsetX = 0;
    let offsetY = 0;

    if (containerRatio > videoRatio) {
      // Pillarboxed (bars on sides)
      renderHeight = height;
      renderWidth = height * videoRatio;
      offsetX = (width - renderWidth) / 2;
    } else {
      // Letterboxed (bars top/bottom)
      renderWidth = width;
      renderHeight = width / videoRatio;
      offsetY = (height - renderHeight) / 2;
    }

    return {
      scaleX: renderWidth / videoWidth,
      scaleY: renderHeight / videoHeight,
      offsetX,
      offsetY,
    };
  }, [width, height, videoWidth, videoHeight]);

  return (
    <svg
      className="absolute inset-0 pointer-events-none z-10"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
    >
      <AnimatePresence>
        {detections.map((student) => {
          // Map coordinates
          const boxWidth = student.bbox.w * scale.scaleX;
          const boxHeight = student.bbox.h * scale.scaleY;
          const x = student.bbox.x * scale.scaleX + scale.offsetX;
          const y = student.bbox.y * scale.scaleY + scale.offsetY;

          const color = emotionColor(student.emotion || "engaged");
          const name = student.student_name || `Unknown #${student.track_id}`;
          const score = student.engagement_score || 0;

          return (
            <motion.g
              key={student.student_id || student.track_id}
              initial={{ opacity: 0 }}
              animate={{ 
                opacity: 1,
                x,
                y
              }}
              exit={{ opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
            >
              {/* Bounding Box */}
              <motion.rect
                width={Math.max(0, boxWidth)}
                height={Math.max(0, boxHeight)}
                fill="transparent"
                stroke={color}
                strokeWidth={2}
                rx={4}
              />

              {/* Phone Detection Pulsing Ring */}
              {student.has_phone && (
                <motion.rect
                  width={Math.max(0, boxWidth + 12)}
                  height={Math.max(0, boxHeight + 12)}
                  x={-6}
                  y={-6}
                  fill="transparent"
                  stroke="#ef4444"
                  strokeWidth={2}
                  rx={8}
                  initial={{ opacity: 0.8, scale: 0.95 }}
                  animate={{ opacity: 0, scale: 1.1 }}
                  transition={{ repeat: Infinity, duration: 1 }}
                />
              )}

              {/* Label Background */}
              <rect
                x={0}
                y={-22}
                width={Math.max(0, boxWidth)}
                height={20}
                fill={color}
                fillOpacity={0.9}
                rx={3}
              />

              {/* Student Name */}
              <text
                x={4}
                y={-8}
                fill="#ffffff"
                fontSize={10}
                fontWeight="bold"
                fontFamily="Inter, sans-serif"
              >
                {name.split(" ")[0]} 
              </text>

              {/* Emotion Emoji */}
              <text
                x={Math.max(0, boxWidth) - 16}
                y={-8}
                fontSize={10}
              >
                {student.emotion === "attentive" ? "🎯" :
                 student.emotion === "engaged" ? "🧠" :
                 student.emotion === "confused" ? "🤔" :
                 student.emotion === "distracted" ? "👀" : "😴"}
              </text>

              {/* Engagement Mini-Bar Background */}
              <rect
                x={0}
                y={Math.max(0, boxHeight) + 4}
                width={Math.max(0, boxWidth)}
                height={4}
                fill="rgba(255,255,255,0.1)"
                rx={2}
              />

              {/* Engagement Mini-Bar Fill */}
              <motion.rect
                x={0}
                y={Math.max(0, boxHeight) + 4}
                height={4}
                fill={color}
                rx={2}
                animate={{ width: Math.max(0, (score / 100) * boxWidth) }}
                transition={{ type: "spring", stiffness: 100 }}
              />
            </motion.g>
          );
        })}
      </AnimatePresence>
    </svg>
  );
}
