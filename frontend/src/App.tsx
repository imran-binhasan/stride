import React, { useEffect, useState } from "react";
import { Navbar } from "./components/Navbar";
import { Sidebar, ViewTab } from "./components/Sidebar";
import { TaskDrawer } from "./components/TaskDrawer";
import { AIDrawer } from "./components/AIDrawer";
import { KanbanPage } from "./pages/KanbanPage";
import { CalendarPage } from "./pages/CalendarPage";
import { GanttPage } from "./pages/GanttPage";
import { TimesheetsPage } from "./pages/TimesheetsPage";
import { AuthPage } from "./pages/AuthPage";
import {
  ActiveTimer,
  GanttChart,
  KanbanBoard,
  Project,
  Task,
  UserProfile,
} from "./types";
import { api } from "./services/api";
import { useRealtime } from "./hooks/useRealtime";
import { X } from "lucide-react";

export const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!api.getToken());
  const [user, setUser] = useState<UserProfile | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [currentTab, setCurrentTab] = useState<ViewTab>("kanban");

  // View States
  const [kanbanBoard, setKanbanBoard] = useState<KanbanBoard | null>(null);
  const [ganttChart, setGanttChart] = useState<GanttChart | null>(null);

  // Active Timer & Modals
  const [activeTimer, setActiveTimer] = useState<ActiveTimer | null>(null);
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [isAIDrawerOpen, setIsAIDrawerOpen] = useState<boolean>(false);
  const [isCreateTaskOpen, setIsCreateTaskOpen] = useState<boolean>(false);

  // New Task Form State
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDesc, setNewTaskDesc] = useState("");
  const [newTaskPriority, setNewTaskPriority] = useState("MEDIUM");
  const [newTaskPoints, setNewTaskPoints] = useState("3");
  const [newTaskDueDate, setNewTaskDueDate] = useState("");

  const refreshUserAndProjects = async () => {
    try {
      const me = await api.getMe();
      setUser(me);

      // Resolve the active organization and its first workspace from the API
      // (the org id also travels as a JWT claim, so requests are always scoped).
      const orgs = await api.listMyOrganizations();
      if (orgs.length === 0) throw new Error("User has no organizations");
      const activeOrgId = api.getOrgId() || orgs[0].id;
      api.setOrg(activeOrgId);

      const workspaces = await api.listWorkspaces(activeOrgId);
      let projList: Project[] = [];
      if (workspaces.length > 0) {
        projList = await api.listWorkspaceProjects(workspaces[0].id);
        // Bootstrap an initial project for a brand-new workspace.
        if (projList.length === 0) {
          const newProj = await api.createProject({
            workspace_id: workspaces[0].id,
            name: "Core Platform",
            key: "STR",
            description: "Main product engineering roadmap",
          });
          projList = [newProj];
        }
      }

      setProjects(projList);
      if (!currentProject && projList.length > 0) {
        setCurrentProject(projList[0]);
      }
    } catch (e) {
      console.error("Auth initialization failed:", e);
      api.clearAuth();
      setIsAuthenticated(false);
    }
  };

  const refreshActiveTimer = async () => {
    try {
      const timer = await api.getActiveTimer();
      setActiveTimer(timer);
    } catch (e) {
      console.error("Timer check failed:", e);
    }
  };

  const refreshCurrentView = async () => {
    if (!currentProject) return;

    try {
      if (currentTab === "kanban") {
        const kb = await api.getKanban(currentProject.id);
        setKanbanBoard(kb);
      } else if (currentTab === "gantt") {
        const gt = await api.getGantt(currentProject.id);
        setGanttChart(gt);
      }
      // Calendar fetches its own data (keyed on month/year) inside CalendarPage.
    } catch (e) {
      console.error("Failed to load view data:", e);
    }
  };

  // Realtime: join the org-scoped room for the current project and refresh on changes.
  const orgId = api.getOrgId();
  const roomName =
    currentProject && orgId ? `room:org:${orgId}:project:${currentProject.id}` : null;
  const { broadcast } = useRealtime(roomName, () => {
    refreshCurrentView();
  });

  // Apply a local mutation, refresh our view, and notify other clients in the room.
  const notifyChange = () => {
    refreshCurrentView();
    broadcast("TASK_UPDATED", {});
  };

  useEffect(() => {
    if (isAuthenticated) {
      refreshUserAndProjects();
      refreshActiveTimer();
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (currentProject) {
      refreshCurrentView();
    }
  }, [currentProject, currentTab]);

  const handleLogout = async () => {
    await api.logout();
    setIsAuthenticated(false);
    setUser(null);
    setProjects([]);
    setCurrentProject(null);
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentProject || !newTaskTitle.trim()) return;

    try {
      await api.createTask({
        project_id: currentProject.id,
        title: newTaskTitle.trim(),
        description: newTaskDesc.trim() || undefined,
        priority: newTaskPriority as any,
        story_points: newTaskPoints ? parseFloat(newTaskPoints) : undefined,
        due_date: newTaskDueDate || undefined,
      });

      setNewTaskTitle("");
      setNewTaskDesc("");
      setIsCreateTaskOpen(false);
      notifyChange();
    } catch (e: any) {
      alert(e.message || "Failed to create task");
    }
  };

  if (!isAuthenticated) {
    return <AuthPage onSuccess={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 overflow-hidden text-slate-100 font-sans">
      {/* Top Navigation */}
      <Navbar
        currentProject={currentProject}
        projects={projects}
        onSelectProject={setCurrentProject}
        activeTimer={activeTimer}
        onRefreshTimer={refreshActiveTimer}
        onOpenAIDrawer={() => setIsAIDrawerOpen(true)}
        user={user}
        onLogout={handleLogout}
      />

      {/* Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          onOpenCreateTask={() => setIsCreateTaskOpen(true)}
        />

        {/* Dynamic Center View */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {currentProject && currentTab === "kanban" && (
            <KanbanPage
              project={currentProject}
              board={kanbanBoard}
              onSelectTask={setSelectedTask}
              onRefresh={notifyChange}
            />
          )}

          {currentProject && currentTab === "calendar" && (
            <CalendarPage project={currentProject} />
          )}

          {currentProject && currentTab === "gantt" && (
            <GanttPage project={currentProject} gantt={ganttChart} />
          )}

          {currentProject && currentTab === "timesheets" && (
            <TimesheetsPage project={currentProject} />
          )}
        </main>
      </div>

      {/* Task Details Drawer */}
      {selectedTask && currentProject && (
        <TaskDrawer
          task={selectedTask}
          statuses={currentProject.statuses || []}
          onClose={() => setSelectedTask(null)}
          onUpdate={() => {
            notifyChange();
            if (selectedTask) {
              api.getTask(selectedTask.id).then(setSelectedTask).catch(console.error);
            }
          }}
          activeTimer={activeTimer}
          onTimerChange={refreshActiveTimer}
        />
      )}

      {/* 5-Gate AI Engineering Drawer */}
      {isAIDrawerOpen && currentProject && (
        <AIDrawer
          projectId={currentProject.id}
          onClose={() => setIsAIDrawerOpen(false)}
        />
      )}

      {/* Quick Create Task Modal */}
      {isCreateTaskOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white tracking-tight">Create New Issue / Task</h3>
              <button onClick={() => setIsCreateTaskOpen(false)} className="p-1 rounded hover:bg-slate-800 text-slate-400">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-4">
              <div>
                <label className="block text-[11px] uppercase font-bold text-slate-400 mb-1">Title</label>
                <input
                  type="text"
                  required
                  placeholder="Task title (e.g. Implement OAuth2 Refresh Token Rotation)"
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>

              <div>
                <label className="block text-[11px] uppercase font-bold text-slate-400 mb-1">Description</label>
                <textarea
                  rows={3}
                  placeholder="Detailed specifications or acceptance criteria..."
                  value={newTaskDesc}
                  onChange={(e) => setNewTaskDesc(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] uppercase font-bold text-slate-400 mb-1">Priority</label>
                  <select
                    value={newTaskPriority}
                    onChange={(e) => setNewTaskPriority(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-2 text-xs text-white"
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                    <option value="URGENT">Urgent</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] uppercase font-bold text-slate-400 mb-1">Story Points</label>
                  <input
                    type="number"
                    value={newTaskPoints}
                    onChange={(e) => setNewTaskPoints(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white"
                  />
                </div>

                <div>
                  <label className="block text-[11px] uppercase font-bold text-slate-400 mb-1">Due Date</label>
                  <input
                    type="date"
                    value={newTaskDueDate}
                    onChange={(e) => setNewTaskDueDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-2 text-xs text-white"
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-2.5 bg-sky-500 hover:bg-sky-400 text-white text-xs font-bold rounded-xl shadow-lg shadow-sky-500/20 transition-all hover:scale-[1.01]"
              >
                Create Task
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
