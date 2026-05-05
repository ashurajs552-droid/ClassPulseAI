"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useTransform, useInView } from "framer-motion";
import Link from "next/link";
import { Zap, Brain, Users, Shield, BarChart3, Camera, ArrowRight, ChevronRight, Sparkles, Eye, Clock, CheckCircle2, Github } from "lucide-react";

// Animated counter
function Counter({ target, suffix = "" }: { target: number; suffix?: string }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  useEffect(() => {
    if (!inView) return;
    let start = 0;
    const step = Math.ceil(target / 40);
    const timer = setInterval(() => { start += step; if (start >= target) { setCount(target); clearInterval(timer); } else setCount(start); }, 30);
    return () => clearInterval(timer);
  }, [inView, target]);
  return <span ref={ref}>{count.toLocaleString()}{suffix}</span>;
}

// Section wrapper with scroll animation
function Section({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.section ref={ref} initial={{ opacity: 0, y: 40 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.7, delay, ease: "easeOut" }} className={className}>
      {children}
    </motion.section>
  );
}

const FEATURES = [
  { icon: Eye, title: "Face Recognition", desc: "FaceNet512 identifies students with 90%+ accuracy in real-time", color: "#6366f1" },
  { icon: Brain, title: "Emotion Detection", desc: "EfficientNetB3 classifies attentive, confused, distracted, engaged, sleepy", color: "#8b5cf6" },
  { icon: Users, title: "Smart Attendance", desc: "Automated AI-powered attendance with confidence scoring", color: "#10b981" },
  { icon: Camera, title: "Phone Detection", desc: "YOLOv8 detects phone usage and generates instant alerts", color: "#f59e0b" },
  { icon: BarChart3, title: "Engagement Analytics", desc: "Per-student engagement scoring with historical trends", color: "#06b6d4" },
  { icon: Shield, title: "Secure & Private", desc: "Edge processing, encrypted embeddings, Supabase RLS policies", color: "#ef4444" },
];

const STEPS = [
  { step: "01", title: "Setup Camera", desc: "Connect any USB or IP camera to your classroom" },
  { step: "02", title: "Enroll Students", desc: "Capture face photos with webcam or upload images" },
  { step: "03", title: "Start Session", desc: "Click start and AI begins monitoring in real-time" },
  { step: "04", title: "Track Everything", desc: "Attendance, emotions, engagement — all automated" },
  { step: "05", title: "Generate Reports", desc: "AI-powered session summaries with actionable insights" },
];

const TECH = [
  "Next.js 14","FastAPI","PyTorch","EfficientNetB3","FaceNet512","YOLOv8","MediaPipe","DeepSORT",
  "Supabase","PostgreSQL","pgvector","Redis","WebSocket","Framer Motion","Recharts","Vercel",
];

export default function LandingPage() {
  const { scrollYProgress } = useScroll();
  const bgY = useTransform(scrollYProgress, [0, 1], [0, -200]);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white overflow-hidden">
      {/* Floating orbs */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <motion.div animate={{ x: [0, 50, 0], y: [0, -30, 0] }} transition={{ duration: 20, repeat: Infinity }} className="absolute top-[10%] left-[15%] w-[500px] h-[500px] rounded-full bg-[#6366f1]/[0.07] blur-[120px]" />
        <motion.div animate={{ x: [0, -40, 0], y: [0, 40, 0] }} transition={{ duration: 25, repeat: Infinity }} className="absolute top-[40%] right-[10%] w-[400px] h-[400px] rounded-full bg-[#8b5cf6]/[0.06] blur-[100px]" />
        <motion.div animate={{ x: [0, 30, 0], y: [0, -50, 0] }} transition={{ duration: 22, repeat: Infinity }} className="absolute bottom-[10%] left-[40%] w-[350px] h-[350px] rounded-full bg-[#06b6d4]/[0.05] blur-[100px]" />
        {/* Dot grid */}
        <div className="absolute inset-0" style={{ backgroundImage: "radial-gradient(rgba(99,102,241,0.08) 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
      </div>

      {/* Navbar */}
      <motion.nav initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="sticky top-0 z-50 backdrop-blur-xl bg-[#0a0a0f]/70 border-b border-white/[0.06]">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center"><Zap className="w-5 h-5 text-white" /></div>
            <span className="text-lg font-bold bg-gradient-to-r from-[#818cf8] via-[#a78bfa] to-[#22d3ee] bg-clip-text text-transparent">ClassPulse AI</span>
          </Link>
          <div className="hidden md:flex items-center gap-6 text-sm text-[#94a3b8]">
            <a href="#features" className="hover:text-white transition">Features</a>
            <a href="#how-it-works" className="hover:text-white transition">How it Works</a>
            <a href="#tech" className="hover:text-white transition">Tech Stack</a>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className="px-4 py-2 text-sm text-[#94a3b8] hover:text-white transition">Sign In</Link>
            <Link href="/login" className="px-5 py-2 text-sm font-medium rounded-xl bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white hover:shadow-[0_0_30px_rgba(99,102,241,0.3)] transition">Get Started</Link>
          </div>
        </div>
      </motion.nav>

      {/* Hero */}
      <section className="relative z-10 max-w-6xl mx-auto px-6 pt-24 pb-20 text-center">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-xs text-[#94a3b8] mb-6">
            <Sparkles className="w-3.5 h-3.5 text-[#f59e0b]" /> AI-Powered Classroom Intelligence
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold leading-tight mb-6">
            <span className="bg-gradient-to-r from-[#818cf8] via-[#a78bfa] to-[#22d3ee] bg-clip-text text-transparent">Transform Your</span><br />
            <span className="text-white">Classroom with AI</span>
          </h1>
          <p className="text-lg md:text-xl text-[#64748b] max-w-2xl mx-auto mb-10">
            Real-time face recognition, emotion detection, and engagement analytics. Monitor 60+ students simultaneously with millisecond latency.
          </p>
          <div className="flex items-center justify-center gap-4 mb-12">
            <Link href="/login" className="px-8 py-3.5 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white font-semibold text-base hover:shadow-[0_0_40px_rgba(99,102,241,0.4)] transition flex items-center gap-2">
              Start Monitoring <ArrowRight className="w-5 h-5" />
            </Link>
            <a href="https://github.com/ashurajs552-droid/ClassPulseAI" target="_blank" className="px-6 py-3.5 rounded-xl bg-white/[0.04] border border-white/[0.08] text-[#94a3b8] font-medium hover:text-white hover:border-white/[0.15] transition flex items-center gap-2">
              <Github className="w-5 h-5" /> View Source
            </a>
          </div>
        </motion.div>
        {/* Stats bar */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }} className="inline-flex items-center gap-8 px-8 py-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] backdrop-blur-sm">
          {[
            { label: "Accuracy", value: <Counter target={95} suffix="%" /> },
            { label: "Students/Frame", value: <Counter target={60} suffix="+" /> },
            { label: "Latency", value: <><Counter target={15} />ms</> },
            { label: "Models", value: <Counter target={5} /> },
          ].map((s, i) => (
            <div key={i} className="text-center">
              <div className="text-2xl font-bold text-white">{s.value}</div>
              <div className="text-[10px] text-[#64748b] uppercase tracking-wider mt-0.5">{s.label}</div>
            </div>
          ))}
        </motion.div>
      </section>

      {/* Features */}
      <Section className="relative z-10 max-w-6xl mx-auto px-6 py-20" delay={0.1}>
        <div id="features" className="text-center mb-14">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">Intelligent Features</h2>
          <p className="text-[#64748b] max-w-lg mx-auto">Everything you need to understand and optimize your classroom</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}
              className="group p-6 rounded-2xl bg-white/[0.03] border border-white/[0.06] backdrop-blur-sm hover:border-white/[0.12] hover:bg-white/[0.05] transition-all duration-300">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4" style={{ background: f.color + "15" }}>
                <f.icon className="w-6 h-6" style={{ color: f.color }} />
              </div>
              <h3 className="text-base font-semibold text-white mb-2">{f.title}</h3>
              <p className="text-sm text-[#64748b] leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* How it Works */}
      <Section className="relative z-10 max-w-4xl mx-auto px-6 py-20" delay={0.1}>
        <div id="how-it-works" className="text-center mb-14">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">How It Works</h2>
          <p className="text-[#64748b]">Five simple steps to smarter classrooms</p>
        </div>
        <div className="relative">
          <div className="absolute left-8 top-0 bottom-0 w-px bg-gradient-to-b from-[#6366f1]/40 via-[#8b5cf6]/30 to-transparent hidden md:block" />
          <div className="space-y-8">
            {STEPS.map((s, i) => (
              <motion.div key={i} initial={{ opacity: 0, x: -30 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.12 }} className="flex items-start gap-6">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-[#6366f1]/20 to-[#8b5cf6]/20 border border-white/[0.08] flex items-center justify-center text-lg font-bold text-[#818cf8] flex-shrink-0">{s.step}</div>
                <div className="pt-2">
                  <h3 className="text-lg font-semibold text-white mb-1">{s.title}</h3>
                  <p className="text-sm text-[#64748b]">{s.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* Tech Stack */}
      <Section className="relative z-10 max-w-5xl mx-auto px-6 py-20" delay={0.1}>
        <div id="tech" className="text-center mb-10">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-3">Tech Stack</h2>
          <p className="text-[#64748b]">Built with cutting-edge technologies</p>
        </div>
        <div className="flex flex-wrap justify-center gap-3">
          {TECH.map((t, i) => (
            <motion.span key={t} initial={{ opacity: 0, scale: 0.8 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }} transition={{ delay: i * 0.04 }}
              className="px-4 py-2 rounded-xl bg-white/[0.04] border border-white/[0.08] text-sm text-[#94a3b8] hover:text-white hover:border-[#6366f1]/30 hover:bg-[#6366f1]/5 transition">{t}</motion.span>
          ))}
        </div>
      </Section>

      {/* Stats */}
      <Section className="relative z-10 max-w-5xl mx-auto px-6 py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { label: "Detection Accuracy", value: 95, suffix: "%" },
            { label: "Max Students/Frame", value: 60, suffix: "+" },
            { label: "Emotion Classes", value: 5, suffix: "" },
            { label: "Inference Speed", value: 15, suffix: "ms" },
          ].map((s, i) => (
            <motion.div key={i} initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }} className="text-center p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06]">
              <div className="text-3xl font-extrabold bg-gradient-to-r from-[#818cf8] to-[#22d3ee] bg-clip-text text-transparent"><Counter target={s.value} suffix={s.suffix} /></div>
              <div className="text-xs text-[#64748b] mt-1.5 uppercase tracking-wider">{s.label}</div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* CTA */}
      <Section className="relative z-10 max-w-3xl mx-auto px-6 py-20">
        <div className="text-center p-10 rounded-3xl bg-gradient-to-br from-[#6366f1]/10 to-[#8b5cf6]/10 border border-[#6366f1]/20 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-[#6366f1]/5 to-transparent" />
          <div className="relative z-10">
            <h2 className="text-3xl font-bold text-white mb-3">Ready to Transform Your Classroom?</h2>
            <p className="text-[#94a3b8] mb-8 max-w-md mx-auto">Start monitoring student engagement in real-time with AI-powered insights.</p>
            <Link href="/login" className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#8b5cf6] text-white font-semibold hover:shadow-[0_0_50px_rgba(99,102,241,0.4)] transition">
              Get Started Free <ChevronRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      </Section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/[0.06] py-8">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center"><Zap className="w-4 h-4 text-white" /></div>
            <span className="text-sm font-semibold text-white">ClassPulse AI</span>
          </div>
          <p className="text-xs text-[#475569]">© 2026 ClassPulse AI. Built by Ashu Raj S.</p>
          <a href="https://github.com/ashurajs552-droid/ClassPulseAI" target="_blank" className="text-xs text-[#64748b] hover:text-white transition flex items-center gap-1"><Github className="w-3.5 h-3.5" /> GitHub</a>
        </div>
      </footer>
    </div>
  );
}
