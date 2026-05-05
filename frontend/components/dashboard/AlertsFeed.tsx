"use client";

import { motion } from "framer-motion";
import { severityColor, timeAgo } from "@/lib/utils";
import { AlertTriangle, Phone, Brain, Moon, HelpCircle, Shield, Check } from "lucide-react";
import type { AlertType } from "@/lib/types";

interface AlertItem {
  id: string; type: AlertType; message: string; severity: string; created_at: string; is_resolved: boolean;
}

interface Props { alerts: AlertItem[]; }

const typeIcon: Record<string, typeof AlertTriangle> = {
  phone_detected: Phone, low_engagement: Brain, mass_sleeping: Moon, high_confusion: HelpCircle, attendance_anomaly: Shield,
};

export default function AlertsFeed({ alerts }: Props) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }} className="glass p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white">Live Alerts</h3>
          <p className="text-[10px] text-[#64748b] mt-0.5">Real-time alert stream</p>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#f59e0b]/10 text-[#f59e0b] font-medium">{alerts.filter(a => !a.is_resolved).length} active</span>
      </div>

      <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
        {alerts.length === 0 ? (
          <div className="text-center py-8 text-[#475569] text-xs">No alerts — classroom is running smoothly ✨</div>
        ) : (
          alerts.map((a, i) => {
            const Icon = typeIcon[a.type] || AlertTriangle;
            return (
              <motion.div
                key={a.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className={`flex items-start gap-3 p-3 rounded-xl border transition-all ${a.is_resolved ? "bg-white/[0.01] border-white/[0.04] opacity-50" : "bg-white/[0.02] border-white/[0.06]"}`}
              >
                <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: severityColor(a.severity) + "15" }}>
                  <Icon className="w-3.5 h-3.5" style={{ color: severityColor(a.severity) }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-white leading-relaxed">{a.message}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{ color: severityColor(a.severity), background: severityColor(a.severity) + "15" }}>{a.severity}</span>
                    <span className="text-[10px] text-[#475569]">{timeAgo(a.created_at)}</span>
                  </div>
                </div>
                {a.is_resolved && <Check className="w-4 h-4 text-[#10b981] flex-shrink-0" />}
              </motion.div>
            );
          })
        )}
      </div>
    </motion.div>
  );
}
