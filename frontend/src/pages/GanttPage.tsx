import React from "react";
import { GanttChart, Project } from "../types";

interface GanttPageProps {
  project: Project;
  gantt: GanttChart | null;
}

export const GanttPage: React.FC<GanttPageProps> = ({ gantt }) => {
  if (!gantt) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        Loading Gantt CPM Chart...
      </div>
    );
  }

  const maxDays = Math.max(gantt.project_duration_days || 1, 14);

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 p-6 select-none overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 shrink-0">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-lg font-bold text-white tracking-tight">Gantt & Critical Path Engine</h1>
            <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-400 border border-red-500/20 text-xs font-semibold">
              Critical Path Method (CPM)
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Total project timeline: <span className="text-white font-bold">{gantt.project_duration_days} Days</span> &bull; {gantt.critical_path.length} tasks on critical bottleneck path
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-400">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-red-500 shadow-sm shadow-red-500/30" />
            <span className="text-white font-medium">Critical Path (0 Float)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-sky-500" />
            <span>Normal Task</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-slate-700" />
            <span>Float Buffer</span>
          </div>
        </div>
      </div>

      {/* Gantt Timeline Table & Visualizer */}
      <div className="flex-1 bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden flex flex-col shadow-sm">
        {/* Timeline Day Header */}
        <div className="flex border-b border-slate-800 bg-slate-900 px-4 py-2.5 text-xs font-bold text-slate-400">
          <div className="w-64 shrink-0">Task & Duration</div>
          <div className="w-24 shrink-0 text-center">Float</div>
          <div className="flex-1 flex text-center font-mono text-[11px] text-slate-500">
            {Array.from({ length: maxDays }).map((_, i) => (
              <span key={i} className="flex-1">D{i + 1}</span>
            ))}
          </div>
        </div>

        {/* Task Rows */}
        <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60 p-2">
          {gantt.nodes.map((node) => {
            const startPct = (node.early_start / maxDays) * 100;
            const widthPct = Math.max(4, (node.duration_days / maxDays) * 100);
            const floatPct = (node.total_float / maxDays) * 100;

            return (
              <div
                key={node.id}
                className="flex items-center px-3 py-3 hover:bg-slate-800/30 transition-colors text-xs"
              >
                {/* Task Label */}
                <div className="w-64 shrink-0 pr-4">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] font-bold text-sky-400">{node.short_id}</span>
                    {node.is_critical && (
                      <span className="w-2 h-2 rounded-full bg-red-400 shadow-sm shadow-red-400 animate-pulse" />
                    )}
                  </div>
                  <p className="text-slate-200 font-medium truncate">{node.title}</p>
                </div>

                {/* Float Time */}
                <div className="w-24 shrink-0 text-center font-mono text-xs">
                  {node.total_float === 0 ? (
                    <span className="text-red-400 font-bold">0d (Crit)</span>
                  ) : (
                    <span className="text-slate-400">+{node.total_float}d float</span>
                  )}
                </div>

                {/* Bar Graph Visualizer */}
                <div className="flex-1 relative h-6 bg-slate-950/60 rounded-md overflow-hidden border border-slate-800">
                  {/* Task Bar */}
                  <div
                    style={{
                      left: `${startPct}%`,
                      width: `${widthPct}%`,
                    }}
                    className={`absolute top-0 bottom-0 rounded flex items-center justify-center font-mono text-[10px] font-bold text-white shadow-sm transition-all ${
                      node.is_critical
                        ? "bg-gradient-to-r from-red-600 to-rose-500 shadow-red-500/20"
                        : "bg-gradient-to-r from-sky-600 to-indigo-600"
                    }`}
                  >
                    {node.duration_days}d
                  </div>

                  {/* Float Buffer Extension Bar */}
                  {node.total_float > 0 && (
                    <div
                      style={{
                        left: `${startPct + widthPct}%`,
                        width: `${floatPct}%`,
                      }}
                      className="absolute top-1 bottom-1 bg-slate-700/40 border-r border-dashed border-slate-500 rounded-r"
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
