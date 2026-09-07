import React, { useEffect, useState } from "react";
import {
  Activity,
  Clock,
  Camera,
  Calendar,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Monitor,
  MousePointer,
  Keyboard,
  Trash2,
  User
} from "lucide-react";
import { DailyActivitySummary, Project } from "../types";
import { api } from "../services/api";

interface TimesheetsPageProps {
  project: Project;
}

export const TimesheetsPage: React.FC<TimesheetsPageProps> = ({ project }) => {
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split("T")[0]);
  const [report, setReport] = useState<DailyActivitySummary | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchReport = async () => {
    try {
      setLoading(true);
      const data = await api.getDailyReport(selectedDate);
      setReport(data);
    } catch (e: any) {
      console.error("Failed to load timesheet report:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, [selectedDate]);

  const formatHours = (seconds: number) => {
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hrs}h ${mins}m`;
  };

  const formatTimeStr = (isoStr?: string | null) => {
    if (!isoStr) return "—";
    return new Date(isoStr).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 p-6 select-none overflow-y-auto space-y-6">
      {/* Header & Date Picker */}
      <div className="flex items-center justify-between shrink-0">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-lg font-bold text-white tracking-tight">Workforce & Screen Intelligence</h1>
            <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-semibold">
              Live Telemetry & Screenshots
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Automated 10-minute activity micro-sampling, proof-of-work captures, and idle deductions
          </p>
        </div>

        {/* Date Filter */}
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-xl p-1.5 shadow-sm">
          <Calendar className="w-4 h-4 text-slate-400 ml-2" />
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="bg-transparent border-0 text-xs font-semibold text-white px-2 py-1 focus:outline-none cursor-pointer"
          />
        </div>
      </div>

      {/* Top 4 Work Metrics Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Shift Span (Day Start -> End) */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-500">Day Shift Span</span>
            <h3 className="text-base font-bold text-white mt-1">
              {formatTimeStr(report?.day_first_start_time)} &rarr; {formatTimeStr(report?.day_last_end_time)}
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {report?.total_sessions_count || 0} active work sessions
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <Clock className="w-5 h-5" />
          </div>
        </div>

        {/* Card 2: Total Worked Time */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-500">Active Worked Time</span>
            <h3 className="text-base font-bold text-emerald-400 mt-1">
              {formatHours(report?.total_work_seconds || 0)}
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Idle: {formatHours(report?.total_idle_seconds || 0)}
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Monitor className="w-5 h-5" />
          </div>
        </div>

        {/* Card 3: Overall Activity Intensity */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-500">Daily Activity Score</span>
            <h3 className="text-base font-bold text-sky-400 mt-1">
              {report?.overall_day_activity_percent || 0}%
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">Weighted input velocity</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Activity className="w-5 h-5" />
          </div>
        </div>

        {/* Card 4: Screenshots Recorded */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between">
          <div>
            <span className="text-[10px] uppercase font-bold text-slate-500">Screenshots Captured</span>
            <h3 className="text-base font-bold text-purple-400 mt-1">
              {report?.total_screenshots_count || 0} Captures
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">S3 Encrypted storage</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Camera className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* 10-Minute Interval Timesheet Timeline */}
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-white">10-Minute Activity Timeline</h3>
            <p className="text-xs text-slate-400">Periodic breakdown of employee keyboard & mouse velocity</p>
          </div>
          <span className="text-xs font-mono text-slate-500">
            {report?.ten_minute_blocks.length || 0} Blocks Tracked
          </span>
        </div>

        {report?.ten_minute_blocks.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No telemetry recorded for this date. Start the timer in the desktop companion app or web dashboard.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {report?.ten_minute_blocks.map((block, idx) => {
              const startStr = new Date(block.block_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
              const endStr = new Date(block.block_end).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

              return (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-slate-800/40 border border-slate-700/60 flex flex-col justify-between space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-white">
                      {startStr} &ndash; {endStr}
                    </span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                        block.is_idle
                          ? "bg-red-500/10 text-red-400 border-red-500/20"
                          : block.activity_percent > 70
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      }`}
                    >
                      {block.is_idle ? "0% (Idle)" : `${block.activity_percent}% Activity`}
                    </span>
                  </div>

                  {/* Activity Progress Bar */}
                  <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden">
                    <div
                      style={{ width: `${block.activity_percent}%` }}
                      className={`h-full rounded-full transition-all ${
                        block.is_idle
                          ? "bg-red-500"
                          : block.activity_percent > 70
                          ? "bg-emerald-400"
                          : "bg-amber-400"
                      }`}
                    />
                  </div>

                  {/* Micro Metrics & Screenshot Thumbnail */}
                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-700/40">
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Keyboard className="w-3 h-3 text-slate-500" />
                        {block.keystroke_count}
                      </span>
                      <span className="flex items-center gap-1">
                        <MousePointer className="w-3 h-3 text-slate-500" />
                        {block.mouse_distance_px}px
                      </span>
                    </div>

                    {block.screenshot_url ? (
                      <span className="text-[10px] font-semibold text-purple-400 flex items-center gap-1">
                        <Camera className="w-3 h-3" />
                        Snapshot Logged
                      </span>
                    ) : (
                      <span className="text-[10px] text-slate-600">No Snapshot</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
