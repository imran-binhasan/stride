import React from "react";
import {
  Kanban,
  Calendar,
  GitBranch,
  Clock,
  Camera,
  Activity,
  Layers,
  Settings,
  ShieldCheck,
  Plus
} from "lucide-react";

export type ViewTab = "kanban" | "calendar" | "gantt" | "timesheets" | "settings";

interface SidebarProps {
  currentTab: ViewTab;
  onSelectTab: (tab: ViewTab) => void;
  onOpenCreateTask: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  onOpenCreateTask,
}) => {
  const navItems: { id: ViewTab; label: string; icon: React.ReactNode; badge?: string }[] = [
    {
      id: "kanban",
      label: "Kanban Board",
      icon: <Kanban className="w-4 h-4" />,
    },
    {
      id: "calendar",
      label: "Calendar View",
      icon: <Calendar className="w-4 h-4" />,
    },
    {
      id: "gantt",
      label: "Gantt Timeline (CPM)",
      icon: <GitBranch className="w-4 h-4" />,
      badge: "CPM",
    },
    {
      id: "timesheets",
      label: "Screen & Workforce Tracking",
      icon: <Activity className="w-4 h-4" />,
      badge: "10m",
    },
  ];

  return (
    <aside className="w-60 border-r border-slate-800 bg-slate-900/50 flex flex-col justify-between shrink-0 select-none p-3">
      <div className="flex flex-col gap-5">
        {/* Quick Action: New Task Button */}
        <button
          onClick={onOpenCreateTask}
          className="w-full py-2 px-3 bg-sky-500 hover:bg-sky-400 active:bg-sky-600 text-white font-medium text-xs rounded-lg flex items-center justify-center gap-2 shadow-lg shadow-sky-500/20 transition-all hover:scale-[1.01]"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          <span>New Task</span>
        </button>

        {/* Navigation Section */}
        <div className="flex flex-col gap-1">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-slate-500 px-2.5 mb-1">
            Views & Management
          </div>

          {navItems.map((item) => {
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? "bg-slate-800 text-sky-400 border border-slate-700/80 shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <span className={isActive ? "text-sky-400" : "text-slate-400"}>
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </div>

                {item.badge && (
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Workforce & Monitoring Highlights */}
        <div className="p-3 rounded-xl bg-slate-800/30 border border-slate-800 flex flex-col gap-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
            <Camera className="w-3.5 h-3.5 text-sky-400" />
            <span>Desktop Companion</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Running 10-minute screen sampling, activity scoring, and idle detection.
          </p>
          <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
            Tauri Daemon Connected
          </div>
        </div>
      </div>

      {/* Footer / Tenant Details */}
      <div className="pt-3 border-t border-slate-800 flex items-center justify-between px-2 text-[11px] text-slate-500">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span>Tenant Isolated (SaaS)</span>
        </div>
        <span className="font-mono text-[10px]">v0.1.0</span>
      </div>
    </aside>
  );
};
