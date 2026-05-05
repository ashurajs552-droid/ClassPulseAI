"use client";

import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import { useEffect, useRef } from "react";
import { Users, Target, AlertTriangle, UserCheck, LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface KPICardProps {
  title: string;
  value: number;
  suffix?: string;
  icon: LucideIcon;
  color: string;
  trend?: number;
  delay?: number;
}

function KPICard({ title, value, suffix = "", icon: Icon, color, trend, delay = 0 }: KPICardProps) {
  const count = useMotionValue(0);
  const rounded = useTransform(count, (v) => suffix === "%" ? v.toFixed(1) + suffix : Math.round(v).toString() + suffix);
  const displayRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const controls = animate(count, value, { duration: 1.5, delay, ease: "easeOut" });
    const unsub = rounded.on("change", (v) => { if (displayRef.current) displayRef.current.textContent = v; });
    return () => { controls.stop(); unsub(); };
  }, [value, count, rounded, delay]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.5 }}
      className="glass p-5 hover:border-white/[0.12] transition-all group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${color}15` }}>
          <Icon className="w-5 h-5" style={{ color }} />
        </div>
        {trend !== undefined && (
          <span className={cn("text-xs font-medium px-2 py-0.5 rounded-full", trend >= 0 ? "text-[#10b981] bg-[#10b981]/10" : "text-[#ef4444] bg-[#ef4444]/10")}>
            {trend >= 0 ? "↑" : "↓"} {Math.abs(trend)}%
          </span>
        )}
      </div>
      <span ref={displayRef} className="text-3xl font-bold text-white block mb-1">0</span>
      <p className="text-xs text-[#64748b] font-medium">{title}</p>
    </motion.div>
  );
}

interface KPICardsProps {
  totalStudents: number;
  attendanceRate: number;
  avgEngagement: number;
  alertsCount: number;
}

export default function KPICards({ totalStudents, attendanceRate, avgEngagement, alertsCount }: KPICardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <KPICard title="Total Students" value={totalStudents} icon={Users} color="#6366f1" trend={2} delay={0} />
      <KPICard title="Attendance Rate" value={attendanceRate} suffix="%" icon={UserCheck} color="#10b981" trend={1.5} delay={0.1} />
      <KPICard title="Avg Engagement" value={avgEngagement} suffix="%" icon={Target} color="#8b5cf6" trend={-0.8} delay={0.2} />
      <KPICard title="Active Alerts" value={alertsCount} icon={AlertTriangle} color="#f59e0b" delay={0.3} />
    </div>
  );
}
