import React, { useEffect, useState } from "react";
import {
  Play,
  Square,
  Zap,
  Activity,
  Clock,
  Camera,
  CheckCircle2,
  Lock,
  Mail,
  User,
  ShieldCheck,
  ChevronDown
} from "lucide-react";

interface TaskItem {
  id: string;
  short_id: string;
  title: string;
  project_name: string;
}

export const App: React.FC = () => {
  const [token, setToken] = useState<string | null>(localStorage.getItem("stride_desktop_token"));
  const [email, setEmail] = useState("lead@stride.io");
  const [password, setPassword] = useState("Password12345!");
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  // Tracking State
  const [isTracking, setIsTracking] = useState(false);
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [activityScore, setActivityScore] = useState(94);
  const [screenshotsToday, setScreenshotsToday] = useState(6);

  // Mock list of assigned tasks for quick start
  const assignedTasks: TaskItem[] = [
    { id: "t1", short_id: "STR-101", title: "Implement OAuth2 Refresh Token Rotation", project_name: "Core Platform" },
    { id: "t2", short_id: "STR-102", title: "Build Critical Path Method Engine", project_name: "Core Platform" },
    { id: "t3", short_id: "STR-103", title: "Wire Up Figma Design Link Resolution", project_name: "Core Platform" },
  ];

  useEffect(() => {
    if (!selectedTask && assignedTasks.length > 0) {
      setSelectedTask(assignedTasks[0]);
    }
  }, []);

  useEffect(() => {
    let interval: any = null;
    if (isTracking) {
      interval = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
        // Random slight fluctuation in activity score to simulate real typing/mouse
        if (Math.random() > 0.7) {
          setActivityScore(Math.floor(85 + Math.random() * 15));
        }
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isTracking]);

  const formatTimer = (sec: number) => {
    const hrs = Math.floor(sec / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    const secs = sec % 60;
    return `${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoggingIn(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        const data = await res.json();
        setToken(data.access_token);
        localStorage.setItem("stride_desktop_token", data.access_token);
      } else {
        alert("Login failed. Make sure backend is running.");
      }
    } catch {
      // Offline fallback token for UI demo
      setToken("offline-token");
      localStorage.setItem("stride_desktop_token", "offline-token");
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleToggleTimer = () => {
    setIsTracking(!isTracking);
  };

  // Login View
  if (!token) {
    return (
      <div className="h-screen w-screen bg-slate-950 p-6 flex flex-col justify-between select-none">
        <div className="space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
              <Zap className="w-4 h-4 text-white fill-white" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">Stride Companion</h2>
              <p className="text-[10px] text-slate-400">Desktop Workforce & Time Tracker</p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-3 pt-2">
            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Company Email</label>
              <div className="relative">
                <Mail className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] uppercase font-bold text-slate-500 mb-1">Password</label>
              <div className="relative">
                <Lock className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoggingIn}
              className="w-full py-2 bg-sky-500 hover:bg-sky-400 text-white text-xs font-bold rounded-lg shadow-md shadow-sky-500/20 transition-all mt-2"
            >
              {isLoggingIn ? "Authenticating..." : "Connect Desktop Tracker"}
            </button>
          </form>
        </div>

        <div className="text-[10px] text-slate-600 text-center flex items-center justify-center gap-1">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span>Unified SaaS Authentication</span>
        </div>
      </div>
    );
  }

  // Active Companion Tracker View
  return (
    <div className="h-screen w-screen bg-slate-950 p-4 flex flex-col justify-between select-none text-slate-100">
      {/* Header Bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center">
            <Zap className="w-3.5 h-3.5 text-white fill-white" />
          </div>
          <span className="text-xs font-bold text-white tracking-tight">STRIDE TRACKER</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[10px] text-slate-400 font-mono">Tauri Daemon</span>
        </div>
      </div>

      {/* Task Picker */}
      <div className="space-y-1.5 my-2">
        <label className="text-[10px] uppercase font-bold text-slate-500">Active Task</label>
        <select
          value={selectedTask?.id || ""}
          onChange={(e) => {
            const t = assignedTasks.find((x) => x.id === e.target.value);
            if (t) setSelectedTask(t);
          }}
          disabled={isTracking}
          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs font-medium text-white focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer disabled:opacity-60"
        >
          {assignedTasks.map((t) => (
            <option key={t.id} value={t.id}>
              {t.short_id}: {t.title}
            </option>
          ))}
        </select>
      </div>

      {/* Big Timer Display & Start/Stop Action */}
      <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 flex flex-col items-center justify-center space-y-3 shadow-inner">
        <span className="text-[11px] uppercase font-bold tracking-widest text-slate-500">
          {isTracking ? "Session Duration" : "Ready to Track"}
        </span>

        <h1 className="text-3xl font-black font-mono tracking-wider text-white">
          {formatTimer(elapsedSeconds)}
        </h1>

        <button
          onClick={handleToggleTimer}
          className={`w-full py-2.5 rounded-xl font-bold text-xs flex items-center justify-center gap-2 shadow-lg transition-all active:scale-95 ${
            isTracking
              ? "bg-red-600 hover:bg-red-500 text-white shadow-red-600/20"
              : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20"
          }`}
        >
          {isTracking ? (
            <>
              <Square className="w-4 h-4 fill-white" />
              <span>Stop & Save Session</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-white" />
              <span>Start Tracking Time</span>
            </>
          )}
        </button>
      </div>

      {/* Live Activity & Telemetry Status Cards */}
      <div className="grid grid-cols-2 gap-2 my-1">
        <div className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-[9px] uppercase font-bold text-slate-500 flex items-center gap-1">
            <Activity className="w-3 h-3 text-sky-400" />
            Activity Intensity
          </span>
          <p className="text-xs font-bold text-sky-400 mt-1">
            {isTracking ? `${activityScore}%` : "—"}
          </p>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800">
          <span className="text-[9px] uppercase font-bold text-slate-500 flex items-center gap-1">
            <Camera className="w-3 h-3 text-purple-400" />
            Screenshots Today
          </span>
          <p className="text-xs font-bold text-purple-400 mt-1">
            {screenshotsToday} Captured
          </p>
        </div>
      </div>

      {/* Footer Info */}
      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-500">
        <span>Runs in Background System Tray</span>
        <button
          onClick={() => {
            localStorage.removeItem("stride_desktop_token");
            setToken(null);
          }}
          className="hover:text-red-400"
        >
          Disconnect
        </button>
      </div>
    </div>
  );
};
