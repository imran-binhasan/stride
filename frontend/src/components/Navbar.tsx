import React, { useEffect, useState } from "react";
import {
  Play,
  Square,
  Sparkles,
  Zap,
  Clock,
  Radio,
  User,
  LogOut,
  FolderKanban,
  CheckCircle2
} from "lucide-react";
import { ActiveTimer, Project, UserProfile } from "../types";
import { api } from "../services/api";

interface NavbarProps {
  currentProject: Project | null;
  projects: Project[];
  onSelectProject: (p: Project) => void;
  activeTimer: ActiveTimer | null;
  onRefreshTimer: () => void;
  onOpenAIDrawer: () => void;
  user: UserProfile | null;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentProject,
  projects,
  onSelectProject,
  activeTimer,
  onRefreshTimer,
  onOpenAIDrawer,
  user,
  onLogout,
}) => {
  const [timerSeconds, setTimerSeconds] = useState<number>(0);
  const [isStopping, setIsStopping] = useState(false);

  useEffect(() => {
    if (!activeTimer) {
      setTimerSeconds(0);
      return;
    }

    const startMs = new Date(activeTimer.start_time).getTime();
    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = Math.floor((now - startMs) / 1000);
      setTimerSeconds(Math.max(0, elapsed));
    }, 1000);

    return () => clearInterval(interval);
  }, [activeTimer]);

  const formatTimer = (sec: number) => {
    const hrs = Math.floor(sec / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    const secs = sec % 60;
    return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const handleStopTimer = async () => {
    try {
      setIsStopping(true);
      await api.stopTimer();
      onRefreshTimer();
    } catch (e: any) {
      alert(e.message || "Failed to stop timer");
    } finally {
      setIsStopping(false);
    }
  };

  return (
    <header className="h-14 border-b border-slate-800 bg-slate-900/90 backdrop-blur px-4 flex items-center justify-between shrink-0 select-none z-20">
      {/* Left: Brand & Project Switcher */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <Zap className="w-4 h-4 text-white fill-white" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-sm tracking-tight text-white flex items-center gap-1.5">
              STRIDE
              <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                PRO
              </span>
            </span>
          </div>
        </div>

        <div className="h-5 w-px bg-slate-800" />

        {/* Project Selector Dropdown */}
        <div className="flex items-center gap-2">
          <FolderKanban className="w-4 h-4 text-slate-400" />
          <select
            value={currentProject?.id || ""}
            onChange={(e) => {
              const p = projects.find((x) => x.id === e.target.value);
              if (p) onSelectProject(p);
            }}
            className="bg-slate-800/80 border border-slate-700/70 hover:border-slate-600 rounded-md px-2.5 py-1 text-xs font-medium text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.key} — {p.name}
              </option>
            ))}
            {projects.length === 0 && <option value="">No projects</option>}
          </select>
        </div>
      </div>

      {/* Center: Active Screen/Workforce Timer Indicator */}
      <div className="flex items-center gap-3">
        {activeTimer ? (
          <div className="flex items-center gap-2.5 px-3 py-1 bg-emerald-950/60 border border-emerald-500/30 rounded-full text-xs font-mono text-emerald-400 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="font-semibold">{formatTimer(timerSeconds)}</span>
            <span className="text-[10px] text-emerald-500/80 font-sans border-l border-emerald-800 pl-2">
              TRACKING ACTIVE
            </span>
            <button
              onClick={handleStopTimer}
              disabled={isStopping}
              title="Stop Active Timer"
              className="ml-1 p-1 hover:bg-emerald-800/50 rounded-full text-emerald-300 transition-colors"
            >
              <Square className="w-3 h-3 fill-emerald-300" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3 py-1 bg-slate-800/40 border border-slate-800 rounded-full text-xs text-slate-400">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span>No Active Timer</span>
          </div>
        )}
      </div>

      {/* Right: AI Pipeline Assistant + Live WebSocket Presence + User Menu */}
      <div className="flex items-center gap-3">
        {/* 5-Gate AI Button */}
        <button
          onClick={onOpenAIDrawer}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-gradient-to-r from-indigo-600 to-sky-600 hover:from-indigo-500 hover:to-sky-500 text-white text-xs font-medium shadow-md shadow-indigo-500/10 transition-all hover:scale-[1.02]"
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>5-Gate AI Engine</span>
        </button>

        {/* Live Presence Pill */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-800/60 border border-slate-700/50 text-[11px] text-slate-300">
          <Radio className="w-3 h-3 text-emerald-400 animate-ping" />
          <span>Live Sync</span>
        </div>

        <div className="h-5 w-px bg-slate-800" />

        {/* User Info & Logout */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-slate-800 transition-colors">
            <div className="w-7 h-7 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-xs font-semibold text-sky-400">
              {user?.full_name?.charAt(0) || "U"}
            </div>
            <div className="hidden md:flex flex-col text-left">
              <span className="text-xs font-medium text-slate-200 leading-tight">
                {user?.full_name || "Employee"}
              </span>
              <span className="text-[10px] text-slate-400 leading-tight">
                {user?.email || "active"}
              </span>
            </div>
          </div>

          <button
            onClick={onLogout}
            title="Log Out"
            className="p-1.5 rounded-md hover:bg-red-500/10 text-slate-400 hover:text-red-400 transition-colors"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};
