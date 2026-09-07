import React, { useEffect, useState } from "react";
import {
  X,
  Play,
  Square,
  Clock,
  CheckSquare,
  Plus,
  Link,
  GitPullRequest,
  ExternalLink,
  Layers,
  Sparkles,
  Calendar,
  AlertCircle,
  Tag
} from "lucide-react";
import { ActiveTimer, FigmaLink, Task, WorkflowStatus } from "../types";
import { api } from "../services/api";

interface TaskDrawerProps {
  task: Task | null;
  statuses: WorkflowStatus[];
  onClose: () => void;
  onUpdate: () => void;
  activeTimer: ActiveTimer | null;
  onTimerChange: () => void;
}

export const TaskDrawer: React.FC<TaskDrawerProps> = ({
  task,
  statuses,
  onClose,
  onUpdate,
  activeTimer,
  onTimerChange,
}) => {
  const [subtaskTitle, setSubtaskTitle] = useState("");
  const [figmaUrl, setFigmaUrl] = useState("");
  const [figmaLinks, setFigmaLinks] = useState<FigmaLink[]>([]);
  const [loadingFigma, setLoadingFigma] = useState(false);
  const [newFieldName, setNewFieldName] = useState("");
  const [newFieldValue, setNewFieldValue] = useState("");
  const [isAddingField, setIsAddingField] = useState(false);

  useEffect(() => {
    if (task) {
      api.listFigmaLinks(task.id).then(setFigmaLinks).catch(console.error);
    }
  }, [task]);

  if (!task) return null;

  const isCurrentTimerActive = activeTimer?.task_id === task.id;

  const handleStartTimer = async () => {
    try {
      await api.startTimer(task.id);
      onTimerChange();
    } catch (e: any) {
      alert(e.message || "Failed to start timer");
    }
  };

  const handleStopTimer = async () => {
    try {
      await api.stopTimer();
      onTimerChange();
    } catch (e: any) {
      alert(e.message || "Failed to stop timer");
    }
  };

  const handleAddSubtask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subtaskTitle.trim()) return;
    try {
      await api.addSubtask(task.id, subtaskTitle);
      setSubtaskTitle("");
      onUpdate();
    } catch (e: any) {
      alert(e.message || "Failed to add subtask");
    }
  };

  const handleAttachFigma = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!figmaUrl.trim()) return;
    try {
      setLoadingFigma(true);
      const link = await api.attachFigma(task.id, figmaUrl);
      setFigmaLinks([...figmaLinks, link]);
      setFigmaUrl("");
    } catch (e: any) {
      alert(e.message || "Failed to attach Figma link");
    } finally {
      setLoadingFigma(false);
    }
  };

  const handleAddCustomField = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFieldName.trim()) return;
    try {
      const updatedFields = { ...(task.custom_fields || {}), [newFieldName.trim()]: newFieldValue.trim() };
      await api.updateTask(task.id, { custom_fields: updatedFields });
      setNewFieldName("");
      setNewFieldValue("");
      setIsAddingField(false);
      onUpdate();
    } catch (e: any) {
      alert(e.message || "Failed to add custom field");
    }
  };

  const handleStatusChange = async (statusId: string) => {
    try {
      await api.updateTask(task.id, { status_id: statusId });
      onUpdate();
    } catch (e: any) {
      alert(e.message || "Failed to update status");
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex justify-end">
      <div className="w-full max-w-2xl bg-slate-900 border-l border-slate-800 h-full flex flex-col shadow-2xl transition-transform duration-200">
        {/* Header */}
        <div className="h-14 border-b border-slate-800 px-5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs font-bold text-sky-400 bg-sky-950/60 border border-sky-800/40 px-2 py-0.5 rounded">
              {task.short_id}
            </span>
            <select
              value={task.status_id}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded px-2 py-0.5 text-xs font-semibold text-slate-200 cursor-pointer focus:outline-none focus:ring-1 focus:ring-sky-500"
            >
              {statuses.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3">
            {/* Active Tracking Controls */}
            {isCurrentTimerActive ? (
              <button
                onClick={handleStopTimer}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded text-xs font-medium transition-colors"
              >
                <Square className="w-3.5 h-3.5 fill-white" />
                <span>Stop Timer</span>
              </button>
            ) : (
              <button
                onClick={handleStartTimer}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium transition-colors shadow-md shadow-emerald-500/10"
              >
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>Track Time</span>
              </button>
            )}

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Title */}
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">{task.title}</h1>
            <p className="text-xs text-slate-400 mt-1">
              Created on {new Date(task.created_at).toLocaleDateString()} by {task.assignee?.full_name || "Team Member"}
            </p>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Description</h3>
            <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-800 text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
              {task.description || "No description provided."}
            </div>
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3.5 rounded-xl bg-slate-800/20 border border-slate-800">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500">Priority</span>
              <p className="text-xs font-semibold text-sky-400 mt-0.5">{task.priority}</p>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500">Story Points</span>
              <p className="text-xs font-semibold text-slate-200 mt-0.5">{task.story_points ?? "—"}</p>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500">Due Date</span>
              <p className="text-xs font-semibold text-slate-200 mt-0.5">{task.due_date ?? "None"}</p>
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-500">Assignee</span>
              <p className="text-xs font-semibold text-slate-200 mt-0.5">{task.assignee?.full_name || "Unassigned"}</p>
            </div>
          </div>

          {/* Dynamic ClickUp-Style Custom Fields */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Tag className="w-3.5 h-3.5 text-sky-400" />
                <span>Custom Fields</span>
              </h3>
              <button
                onClick={() => setIsAddingField(!isAddingField)}
                className="text-xs text-sky-400 hover:text-sky-300 font-medium flex items-center gap-1"
              >
                <Plus className="w-3 h-3" />
                Add Field
              </button>
            </div>

            {isAddingField && (
              <form onSubmit={handleAddCustomField} className="flex gap-2 p-2.5 rounded-lg bg-slate-800/60 border border-slate-700">
                <input
                  type="text"
                  placeholder="Field Name (e.g. Budget, Client)"
                  value={newFieldName}
                  onChange={(e) => setNewFieldName(e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
                <input
                  type="text"
                  placeholder="Value"
                  value={newFieldValue}
                  onChange={(e) => setNewFieldValue(e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-sky-500"
                />
                <button
                  type="submit"
                  className="px-3 py-1 bg-sky-500 hover:bg-sky-400 text-white rounded text-xs font-medium"
                >
                  Save
                </button>
              </form>
            )}

            <div className="grid grid-cols-2 gap-2">
              {Object.entries(task.custom_fields || {}).map(([key, val]) => (
                <div key={key} className="p-2.5 rounded-lg bg-slate-800/30 border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-bold">{key}</span>
                  <p className="text-xs font-medium text-slate-200 mt-0.5">{String(val)}</p>
                </div>
              ))}
              {Object.keys(task.custom_fields || {}).length === 0 && !isAddingField && (
                <p className="text-xs text-slate-500 col-span-2">No custom fields added yet.</p>
              )}
            </div>
          </div>

          {/* Subtasks Checklist */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <CheckSquare className="w-3.5 h-3.5 text-emerald-400" />
              <span>Subtasks ({task.subtasks?.length || 0})</span>
            </h3>

            <div className="space-y-1.5">
              {task.subtasks?.map((sub) => (
                <div
                  key={sub.id}
                  className="flex items-center gap-2.5 p-2 rounded-lg bg-slate-800/30 border border-slate-800/80 text-xs text-slate-200"
                >
                  <input
                    type="checkbox"
                    checked={sub.is_completed}
                    readOnly
                    className="w-3.5 h-3.5 rounded bg-slate-700 border-slate-600 text-sky-500 focus:ring-0 cursor-pointer"
                  />
                  <span className={sub.is_completed ? "line-through text-slate-500" : ""}>{sub.title}</span>
                </div>
              ))}
            </div>

            <form onSubmit={handleAddSubtask} className="flex gap-2">
              <input
                type="text"
                placeholder="Add subtask item..."
                value={subtaskTitle}
                onChange={(e) => setSubtaskTitle(e.target.value)}
                className="flex-1 bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
              <button
                type="submit"
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700"
              >
                Add
              </button>
            </form>
          </div>

          {/* Figma Design Embeds */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <Link className="w-3.5 h-3.5 text-purple-400" />
              <span>Figma Design Frames</span>
            </h3>

            <div className="space-y-2">
              {figmaLinks.map((link) => (
                <a
                  key={link.id}
                  href={link.figma_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between p-3 rounded-lg bg-purple-950/20 border border-purple-800/30 hover:border-purple-600/50 text-xs text-purple-300 transition-all group"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="font-semibold text-white">{link.file_name}</span>
                    <span className="text-[10px] text-purple-400 font-mono">Node: {link.node_id || "Root"}</span>
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100" />
                </a>
              ))}
            </div>

            <form onSubmit={handleAttachFigma} className="flex gap-2">
              <input
                type="url"
                placeholder="https://figma.com/design/..."
                value={figmaUrl}
                onChange={(e) => setFigmaUrl(e.target.value)}
                className="flex-1 bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
              />
              <button
                type="submit"
                disabled={loadingFigma}
                className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium rounded-lg shadow-md shadow-purple-500/10"
              >
                {loadingFigma ? "Linking..." : "Attach"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
