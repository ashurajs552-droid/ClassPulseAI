"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { LayoutDashboard, Video, UserCheck, BarChart3, FileText, Users, Settings, Zap, LogOut, ChevronLeft, ChevronRight, Radio, Moon, Sun } from "lucide-react";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { supabase, signOut } from "@/lib/supabase";
import { useTheme } from "next-themes";

const nav = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/live", icon: Video, label: "Live Monitor" },
  { href: "/attendance", icon: UserCheck, label: "Attendance" },
  { href: "/analytics", icon: BarChart3, label: "Analytics" },
  { href: "/reports", icon: FileText, label: "AI Reports" },
  { href: "/students", icon: Users, label: "Students" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [userName, setUserName] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    supabase.auth.getUser().then(({ data: { user } }) => {
      if (user) {
        setUserName(user.user_metadata?.full_name || user.email?.split("@")[0] || "User");
        setUserEmail(user.email || "");
      }
    });
  }, []);

  const handleLogout = async () => {
    await signOut();
    router.replace("/login");
  };

  return (
    <motion.aside
      animate={{ width: collapsed ? 72 : 256 }}
      transition={{ duration: 0.25, ease: "easeInOut" }}
      className="fixed left-0 top-0 h-screen z-50 flex flex-col border-r border-white/[0.06] bg-white dark:bg-[#0a0a0f]/97 backdrop-blur-xl"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 h-16 border-b border-black/[0.06] dark:border-white/[0.06] flex-shrink-0">
        <div className="relative flex-shrink-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-[#10b981] border-2 border-white dark:border-[#0a0a0f]" />
        </div>
        <AnimatePresence>
          {!collapsed && (
            <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }}>
              <h1 className="text-base font-bold text-slate-900 dark:text-transparent dark:bg-gradient-to-r dark:from-[#818cf8] dark:to-[#22d3ee] dark:bg-clip-text leading-tight">ClassPulse</h1>
              <p className="text-[9px] text-slate-500 dark:text-[#64748b] tracking-[0.15em] uppercase">AI Monitor</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Status */}
      <AnimatePresence>
        {!collapsed && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mx-3 mt-3 mb-1 px-3 py-2 rounded-lg bg-[#10b981]/10 border border-[#10b981]/20">
            <div className="flex items-center gap-2">
              <Radio className="w-3 h-3 text-[#10b981] animate-pulse" />
              <span className="text-[10px] text-[#10b981] font-medium tracking-wide">SYSTEM ONLINE</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {nav.map((item) => {
          const active = pathname === item.href;
          return (
            <Link key={item.href} href={item.href}>
              <div className={cn(
                "group flex items-center gap-3 px-3 py-2.5 rounded-xl relative transition-all duration-200",
                active ? "bg-[#6366f1]/10 dark:bg-[#6366f1]/12 text-[#6366f1] dark:text-white" : "text-slate-600 dark:text-[#64748b] hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.03]"
              )}>
                {active && (
                  <motion.div layoutId="activeNav" className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-[#6366f1]" transition={{ type: "spring", stiffness: 300, damping: 30 }} />
                )}
                <item.icon className={cn("w-[18px] h-[18px] flex-shrink-0", active && "text-[#6366f1] dark:text-[#818cf8]")} />
                <AnimatePresence>
                  {!collapsed && (
                    <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-[13px] font-medium">{item.label}</motion.span>
                  )}
                </AnimatePresence>
              </div>
            </Link>
          );
        })}
      </nav>

      {/* User / Logout */}
      <div className="px-3 py-3 border-t border-black/[0.06] dark:border-white/[0.06] space-y-2">
        {!collapsed && (
          <div className="flex items-center gap-2.5 px-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[#6366f1] to-[#8b5cf6] flex items-center justify-center text-xs font-bold text-white">
              {userName.charAt(0).toUpperCase()}
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-medium text-slate-900 dark:text-white truncate">{userName}</p>
              <p className="text-[10px] text-slate-500 dark:text-[#64748b] truncate">{userEmail}</p>
            </div>
          </div>
        )}
        <div className="flex gap-1">
          <button onClick={handleLogout} title="Sign Out" className={cn("flex items-center gap-2 py-2 rounded-lg text-slate-500 dark:text-[#64748b] hover:text-[#ef4444] dark:hover:text-[#ef4444] hover:bg-[#ef4444]/10 transition", collapsed ? "justify-center w-full px-2" : "px-3 flex-1")}>
            <LogOut className="w-4 h-4" />
            {!collapsed && <span className="text-xs">Sign Out</span>}
          </button>
          {mounted && (
            <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")} title="Toggle Theme" className="py-2 px-2 rounded-lg text-slate-500 dark:text-[#64748b] hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.04] transition">
              {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          )}
          <button onClick={() => setCollapsed(!collapsed)} title="Toggle Sidebar" className="py-2 px-2 rounded-lg text-slate-500 dark:text-[#64748b] hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/[0.04] transition">
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </motion.aside>
  );
}
