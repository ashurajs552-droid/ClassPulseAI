"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Sparkles, Download, ChevronRight, X, Lightbulb, Target, AlertTriangle, Star, Loader2 } from "lucide-react";
import { engagementGrade } from "@/lib/utils";

const REPORTS = [
  {
    id: "r1", title: "Session Report — May 4, 2026", session: "CS 101 — 9:00 AM", date: "2026-05-04",
    engagement: 78.5,
    summary: "The session showed strong overall engagement with 91% attendance. A brief dip in attention was observed around the 45-minute mark, correlating with complex topic introduction. Three students were flagged for consistently low engagement.",
    insights: [
      { title: "Attendance Peak", description: "92% students arrived within the first 5 minutes — best this month.", icon: "star" },
      { title: "Engagement Dip", description: "Class engagement dropped 18% at 09:45 during recursion topic.", icon: "alert" },
      { title: "Top Performer", description: "Aanya Sharma maintained 94% engagement throughout.", icon: "target" },
      { title: "Phone Alert", description: "2 phone detections recorded, both near window seats.", icon: "alert" },
    ],
    recommendations: [
      "Introduce a 5-minute interactive activity at the 40-minute mark to prevent attention drop-off.",
      "Consider paired programming exercises for the recursion segment.",
      "Schedule a check-in with Liam O'Brien regarding declining engagement trend.",
      "Move phone-prone students away from window seats.",
    ],
  },
  {
    id: "r2", title: "Session Report — May 2, 2026", session: "CS 101 — 9:00 AM", date: "2026-05-02",
    engagement: 82.1,
    summary: "Excellent session with high engagement throughout. Lab-based activity in the second half significantly boosted class participation. No major alerts.",
    insights: [
      { title: "Best Session", description: "Highest avg engagement this week at 82.1%.", icon: "star" },
      { title: "Lab Activity", description: "Engagement rose 23% during hands-on lab segment.", icon: "target" },
    ],
    recommendations: [
      "Continue incorporating hands-on activities in each session.",
      "Use this session's format as a template for future lectures.",
    ],
  },
];

const iconMap: Record<string, typeof Star> = { star: Star, alert: AlertTriangle, target: Target, chart: Lightbulb };

export default function ReportsPage() {
  const [generating, setGenerating] = useState(false);
  const [selectedReport, setSelectedReport] = useState<typeof REPORTS[0] | null>(null);

  const handleGenerate = async () => {
    setGenerating(true);
    await new Promise(r => setTimeout(r, 3000));
    setGenerating(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Reports</h1>
          <p className="text-sm text-[#64748b] mt-0.5">Claude-powered session analysis and insights</p>
        </div>
        <motion.button
          whileTap={{ scale: 0.95 }}
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white font-medium text-sm hover:shadow-[0_0_30px_rgba(99,102,241,0.3)] transition disabled:opacity-60"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {generating ? "AI is analyzing…" : "Generate Report"}
        </motion.button>
      </div>

      {/* Loading state */}
      <AnimatePresence>
        {generating && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="glass p-8 text-center">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] mx-auto mb-4 flex items-center justify-center animate-pulse-glow">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">AI is analyzing your session…</h3>
            <p className="text-sm text-[#64748b]">Processing engagement data, emotion patterns, and generating insights</p>
            <div className="mt-4 flex justify-center gap-1">
              {[0, 1, 2].map(i => <motion.div key={i} animate={{ scale: [1, 1.3, 1] }} transition={{ repeat: Infinity, delay: i * 0.2, duration: 0.8 }} className="w-2 h-2 rounded-full bg-[#6366f1]" />)}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Report cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {REPORTS.map((r, i) => {
          const g = engagementGrade(r.engagement);
          return (
            <motion.div key={r.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }} className="glass p-5 hover:border-white/[0.12] transition cursor-pointer group" onClick={() => setSelectedReport(r)}>
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[#6366f1]/10 flex items-center justify-center">
                    <FileText className="w-5 h-5 text-[#818cf8]" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">{r.title}</h3>
                    <p className="text-[10px] text-[#64748b] mt-0.5">{r.session}</p>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{ color: g.color, background: g.color + "15" }}>{r.engagement}%</span>
              </div>
              <p className="text-xs text-[#94a3b8] line-clamp-2 mb-4">{r.summary}</p>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[10px] text-[#475569]">
                  <Sparkles className="w-3 h-3 text-[#6366f1]" />
                  {r.insights.length} insights · {r.recommendations.length} recommendations
                </div>
                <div className="flex items-center gap-2">
                  <button className="text-[#64748b] hover:text-white transition"><Download className="w-4 h-4" /></button>
                  <ChevronRight className="w-4 h-4 text-[#64748b] group-hover:text-[#6366f1] transition" />
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Full Report Modal */}
      <AnimatePresence>
        {selectedReport && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedReport(null)}>
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }} onClick={e => e.stopPropagation()} className="glass-strong w-full max-w-3xl max-h-[85vh] overflow-y-auto p-8">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-white">{selectedReport.title}</h2>
                  <p className="text-xs text-[#64748b] mt-0.5">{selectedReport.session}</p>
                </div>
                <button onClick={() => setSelectedReport(null)} className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center text-[#64748b] hover:text-white transition"><X className="w-4 h-4" /></button>
              </div>

              {/* Summary */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-[#818cf8] mb-2 flex items-center gap-2"><FileText className="w-4 h-4" /> Executive Summary</h3>
                <p className="text-sm text-[#94a3b8] leading-relaxed">{selectedReport.summary}</p>
              </div>

              {/* Key Insights */}
              <div className="mb-6">
                <h3 className="text-sm font-semibold text-[#818cf8] mb-3 flex items-center gap-2"><Lightbulb className="w-4 h-4" /> Key Insights</h3>
                <div className="space-y-2">
                  {selectedReport.insights.map((ins, i) => {
                    const Icon = iconMap[ins.icon] || Lightbulb;
                    return (
                      <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1 }} className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                        <div className="w-7 h-7 rounded-lg bg-[#6366f1]/10 flex items-center justify-center flex-shrink-0"><Icon className="w-3.5 h-3.5 text-[#818cf8]" /></div>
                        <div>
                          <p className="text-xs font-medium text-white">{ins.title}</p>
                          <p className="text-xs text-[#94a3b8] mt-0.5">{ins.description}</p>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </div>

              {/* Recommendations */}
              <div>
                <h3 className="text-sm font-semibold text-[#818cf8] mb-3 flex items-center gap-2"><Target className="w-4 h-4" /> Recommendations</h3>
                <div className="space-y-2">
                  {selectedReport.recommendations.map((rec, i) => (
                    <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.1 }} className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                      <span className="w-5 h-5 rounded-full bg-[#10b981]/10 flex items-center justify-center text-[10px] font-bold text-[#10b981] flex-shrink-0">{i + 1}</span>
                      <p className="text-xs text-[#94a3b8]">{rec}</p>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
