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
  Plus,
  Table2
} from "lucide-react";

export type ViewTab = "kanban" | "calendar" | "gantt" | "timesheets" | "table" | "settings" | "workforce" | "billing" | "platform";

interface SidebarProps {
  isSuperadmin?: boolean;
  currentTab: ViewTab;
  onSelectTab: (tab: ViewTab) => void;
  onOpenCreateTask: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isSuperadmin = false,
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
    {id: "table", label: "Issue table", icon: <Table2 className="w-4 h-4" />},
    {id: "workforce", label: "People & payroll", icon: <Layers className="w-4 h-4" />},
    {id: "billing", label: "Billing", icon: <ShieldCheck className="w-4 h-4" />},
    {id: "settings", label: "Workspace settings", icon: <Settings className="w-4 h-4" />},
    {
      id: "timesheets",
      label: "Time & activity",
      icon: <Activity className="w-4 h-4" />,

    },
  ];
  const items = [...navItems];
  if (isSuperadmin) {
    items.push({ id: "platform", label: "Platform administration", icon: <ShieldCheck className="w-4 h-4" /> });
  }

  return (
    <aside className="w-16 md:w-56 border-r border-slate-800 bg-slate-900/50 flex flex-col justify-between shrink-0 select-none p-3">
      <div className="flex flex-col gap-5">
        {/* Quick Action: New Task Button */}
        <button
          onClick={onOpenCreateTask}
          className="w-full py-2 px-3 bg-sky-500 hover:bg-sky-400 active:bg-sky-600 text-white font-medium text-xs rounded-lg flex items-center justify-center gap-2 shadow-lg shadow-sky-500/20 transition-all hover:scale-[1.01]"
        >
          <Plus className="w-4 h-4 stroke-[2.5]" />
          <span className="hidden md:inline">New Task</span>
        </button>

        {/* Navigation Section */}
        <div className="flex flex-col gap-1">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-slate-500 px-2.5 mb-1">
            <span className="hidden md:inline">Views & Management</span>
          </div>

          {items.map((item) => {
            const isActive = currentTab === item.id;
            return (
              <button
                title={item.label}
                aria-label={item.label}
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
                  <span className="hidden md:inline">{item.label}</span>
                </div>

                {item.badge && (
                  <span className="hidden md:inline text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>


      </div>

      {/* Footer / Tenant Details */}
      <div className="pt-3 border-t border-slate-800 flex items-center justify-between px-2 text-[11px] text-slate-500">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span className="hidden md:inline">Stride workspace</span>
        </div>
        <span className="hidden md:inline font-mono text-[10px]">v0.1.0</span>
      </div>
    </aside>
  );
};
