import React, { useState } from "react";
import {
  Plus,
  MoreVertical,
  CheckCircle2,
  Clock,
  User,
  AlertCircle,
  Tag,
  Layers,
  Sparkles,
  ArrowRight,
  ArrowLeft
} from "lucide-react";
import { KanbanBoard, Project, Task, WorkflowStatus } from "../types";
import { api } from "../services/api";

interface KanbanPageProps {
  project: Project;
  board: KanbanBoard | null;
  onSelectTask: (task: Task) => void;
  onRefresh: () => void;
}

export const KanbanPage: React.FC<KanbanPageProps> = ({
  project,
  board,
  onSelectTask,
  onRefresh,
}) => {
  const [isAddingStatus, setIsAddingStatus] = useState(false);
  const [newStatusName, setNewStatusName] = useState("");
  const [newStatusColor, setNewStatusColor] = useState("#3B82F6");
  const [newStatusCategory, setNewStatusCategory] = useState("TODO");

  const handleCreateStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStatusName.trim()) return;

    try {
      await api.addCustomStatus(project.id, {
        name: newStatusName.trim(),
        color: newStatusColor,
        category: newStatusCategory,
        position: (board?.columns.length || 0) * 10,
      });
      setNewStatusName("");
      setIsAddingStatus(false);
      onRefresh();
    } catch (e: any) {
      alert(e.message || "Failed to add status");
    }
  };

  const handleMoveTask = async (taskId: string, targetStatusId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.moveTask(taskId, targetStatusId, 1000);
      onRefresh();
    } catch (e: any) {
      alert(e.message || "Failed to move task");
    }
  };

  if (!board) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500">
        Loading Kanban Board...
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-x-auto bg-slate-950 p-6 select-none">
      {/* Board Header Actions */}
      <div className="flex items-center justify-between mb-6 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-white tracking-tight">{project.name}</h1>
          <span className="px-2.5 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-400">
            {board.total_tasks} Total Issues
          </span>
        </div>

        {/* Add Custom Status Column (ClickUp Style) */}
        <div className="flex items-center gap-2">
          {isAddingStatus ? (
            <form onSubmit={handleCreateStatus} className="flex items-center gap-2 bg-slate-900 border border-slate-700 rounded-lg p-1.5 shadow-lg">
              <input
                type="text"
                placeholder="Column Name (e.g. QA Review)"
                value={newStatusName}
                onChange={(e) => setNewStatusName(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
              <select
                value={newStatusCategory}
                onChange={(e) => setNewStatusCategory(e.target.value)}
                className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200"
              >
                <option value="BACKLOG">Backlog</option>
                <option value="TODO">To Do</option>
                <option value="IN_PROGRESS">In Progress</option>
                <option value="IN_REVIEW">In Review</option>
                <option value="DONE">Done</option>
              </select>
              <input
                type="color"
                value={newStatusColor}
                onChange={(e) => setNewStatusColor(e.target.value)}
                className="w-7 h-7 rounded border border-slate-700 cursor-pointer bg-transparent"
              />
              <button
                type="submit"
                className="px-2.5 py-1 bg-sky-500 hover:bg-sky-400 text-white rounded text-xs font-semibold"
              >
                Add
              </button>
              <button
                type="button"
                onClick={() => setIsAddingStatus(false)}
                className="px-2 py-1 text-slate-400 hover:text-white text-xs"
              >
                Cancel
              </button>
            </form>
          ) : (
            <button
              onClick={() => setIsAddingStatus(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-medium transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Custom Column</span>
            </button>
          )}
        </div>
      </div>

      {/* Kanban Board Columns */}
      <div className="flex-1 flex gap-5 overflow-x-auto pb-4 items-start">
        {board.columns.map((col, colIndex) => {
          const prevCol = colIndex > 0 ? board.columns[colIndex - 1] : null;
          const nextCol = colIndex < board.columns.length - 1 ? board.columns[colIndex + 1] : null;

          return (
            <div
              key={col.status.id}
              className="w-80 shrink-0 bg-slate-900/60 border border-slate-800 rounded-xl flex flex-col max-h-full overflow-hidden shadow-sm"
            >
              {/* Column Header */}
              <div className="p-3.5 border-b border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full"
                    style={{ backgroundColor: col.status.color || "#6B7280" }}
                  />
                  <h3 className="font-semibold text-xs text-white tracking-tight uppercase">
                    {col.status.name}
                  </h3>
                </div>
                <span className="text-xs font-mono font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700/60">
                  {col.task_count}
                </span>
              </div>

              {/* Task Cards Container */}
              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                {col.tasks.map((task) => (
                  <div
                    key={task.id}
                    onClick={() => onSelectTask(task)}
                    className="p-3.5 rounded-xl bg-slate-800/40 hover:bg-slate-800/80 border border-slate-700/60 hover:border-slate-600 transition-all cursor-pointer shadow-sm group space-y-2.5"
                  >
                    {/* Top Row: Short ID & Priority */}
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] font-bold text-sky-400">
                        {task.short_id}
                      </span>
                      <span
                        className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${
                          task.priority === "URGENT"
                            ? "bg-red-500/10 text-red-400 border-red-500/20"
                            : task.priority === "HIGH"
                            ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                            : "bg-slate-700/30 text-slate-400 border-slate-700"
                        }`}
                      >
                        {task.priority}
                      </span>
                    </div>

                    {/* Title */}
                    <h4 className="text-xs font-medium text-slate-200 group-hover:text-white leading-snug">
                      {task.title}
                    </h4>

                    {/* Dynamic Custom Fields Tags (ClickUp style) */}
                    {task.custom_fields && Object.keys(task.custom_fields).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {Object.entries(task.custom_fields).map(([k, v]) => (
                          <span
                            key={k}
                            className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-900 border border-slate-700/60 text-slate-300"
                          >
                            <span className="text-slate-500 font-bold">{k}:</span> {String(v)}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Bottom Metadata & Move Controls */}
                    <div className="pt-2 border-t border-slate-700/40 flex items-center justify-between text-[11px] text-slate-400">
                      <div className="flex items-center gap-2">
                        <div className="w-5 h-5 rounded-full bg-slate-700 flex items-center justify-center text-[10px] font-bold text-slate-300">
                          {task.assignee?.full_name?.charAt(0) || "U"}
                        </div>
                        {task.story_points && (
                          <span className="font-mono text-slate-400">{task.story_points} pts</span>
                        )}
                      </div>

                      {/* 1-Click Move Arrows */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {prevCol && (
                          <button
                            onClick={(e) => handleMoveTask(task.id, prevCol.status.id, e)}
                            title={`Move to ${prevCol.status.name}`}
                            className="p-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-200"
                          >
                            <ArrowLeft className="w-3 h-3" />
                          </button>
                        )}
                        {nextCol && (
                          <button
                            onClick={(e) => handleMoveTask(task.id, nextCol.status.id, e)}
                            title={`Move to ${nextCol.status.name}`}
                            className="p-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-200"
                          >
                            <ArrowRight className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {col.tasks.length === 0 && (
                  <div className="h-28 border border-dashed border-slate-800 rounded-xl flex items-center justify-center text-xs text-slate-600">
                    No issues
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
