"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Sparkles, Download, ChevronRight, X, Lightbulb, Target, AlertTriangle, Star, Loader2, Inbox } from "lucide-react";
import { engagementGrade, cn } from "@/lib/utils";
import { supabase } from "@/lib/supabase";

const iconMap: Record<string, typeof Star> = { star: Star, alert: AlertTriangle, target: Target, chart: Lightbulb };

export default function ReportsPage() {
  const [generating, setGenerating] = useState(false);
  const [reports, setReports] = useState<any[]>([]);
  const [selectedReport, setSelectedReport] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const { data } = await supabase
        .from("reports")
        .select("*, sessions(started_at, classes(name))")
        .order("generated_at", { ascending: false });
      setReports(data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    // In a real app, this would trigger an edge function or backend endpoint
    // to generate the report via Anthropic API and save it to the DB.
    setTimeout(() => {
      setGenerating(false);
      fetchReports();
    }, 3000);
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

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 text-[#6366f1] animate-spin" /></div>
      ) : reports.length === 0 ? (
        <div className="text-center py-20 glass">
          <Inbox className="w-12 h-12 text-[#1e293b] mx-auto mb-4" />
          <p className="text-lg font-medium text-white">No reports generated yet</p>
          <p className="text-sm text-[#475569] mt-1">Click "Generate Report" after a session completes.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {reports.map((r, i) => {
            const engScore = r.metrics_snapshot?.avg_engagement || 0;
            const g = engagementGrade(engScore);
            const className = r.sessions?.classes?.name || "Unknown Class";
            const sessionDate = r.sessions?.started_at ? new Date(r.sessions.started_at).toLocaleString() : "Unknown Date";
            
            return (
              <motion.div key={r.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }} className="glass p-5 hover:border-white/[0.12] transition cursor-pointer group" onClick={() => setSelectedReport(r)}>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-[#6366f1]/10 flex items-center justify-center">
                      <FileText className="w-5 h-5 text-[#818cf8]" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-white">{r.title}</h3>
                      <p className="text-[10px] text-[#64748b] mt-0.5">{className} — {sessionDate}</p>
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{ color: g.color, background: g.color + "15" }}>{engScore}%</span>
                </div>
                <p className="text-xs text-[#94a3b8] line-clamp-2 mb-4">{r.summary}</p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-[10px] text-[#475569]">
                    <Sparkles className="w-3 h-3 text-[#6366f1]" />
                    {r.insights?.length || 0} insights · {r.recommendations?.length || 0} recommendations
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="text-[#64748b] hover:text-white transition" onClick={(e) => { e.stopPropagation(); window.open(r.pdf_url, '_blank'); }} disabled={!r.pdf_url}>
                      <Download className="w-4 h-4" />
                    </button>
                    <ChevronRight className="w-4 h-4 text-[#64748b] group-hover:text-[#6366f1] transition" />
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Full Report Modal */}
      <AnimatePresence>
        {selectedReport && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedReport(null)}>
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }} onClick={e => e.stopPropagation()} className="glass-strong w-full max-w-3xl max-h-[85vh] overflow-y-auto p-8">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-white">{selectedReport.title}</h2>
                  <p className="text-xs text-[#64748b] mt-0.5">{selectedReport.sessions?.classes?.name} — {selectedReport.sessions?.started_at ? new Date(selectedReport.sessions.started_at).toLocaleString() : ""}</p>
                </div>
                <button onClick={() => setSelectedReport(null)} className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center text-[#64748b] hover:text-white transition"><X className="w-4 h-4" /></button>
              </div>

              {/* Summary */}
              {selectedReport.summary && (
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-[#818cf8] mb-2 flex items-center gap-2"><FileText className="w-4 h-4" /> Executive Summary</h3>
                  <p className="text-sm text-[#94a3b8] leading-relaxed">{selectedReport.summary}</p>
                </div>
              )}

              {/* Key Insights */}
              {selectedReport.insights && selectedReport.insights.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-[#818cf8] mb-3 flex items-center gap-2"><Lightbulb className="w-4 h-4" /> Key Insights</h3>
                  <div className="space-y-2">
                    {selectedReport.insights.map((ins: any, i: number) => {
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
              )}

              {/* Recommendations */}
              {selectedReport.recommendations && selectedReport.recommendations.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-[#818cf8] mb-3 flex items-center gap-2"><Target className="w-4 h-4" /> Recommendations</h3>
                  <div className="space-y-2">
                    {selectedReport.recommendations.map((rec: string, i: number) => (
                      <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + i * 0.1 }} className="flex items-start gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                        <span className="w-5 h-5 rounded-full bg-[#10b981]/10 flex items-center justify-center text-[10px] font-bold text-[#10b981] flex-shrink-0">{i + 1}</span>
                        <p className="text-xs text-[#94a3b8]">{rec}</p>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
