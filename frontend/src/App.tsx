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
import { TablePage } from "./pages/TablePage";
import { SettingsPage } from "./pages/SettingsPage";
import { MyOrg, Workspace, OrgMember } from "./types";

export const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!api.getToken());
  const [user, setUser] = useState<UserProfile | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [currentTab, setCurrentTab] = useState<ViewTab>("kanban");

  const [organizations, setOrganizations] = useState<MyOrg[]>([]);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [members, setMembers] = useState<OrgMember[]>([]);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [initializing, setInitializing] = useState(true);
  const [creating, setCreating] = useState(false);
  const activeOrg = organizations.find(org => org.id === api.getOrgId()) || null;
  const canManage = !!activeOrg && ["ORG_OWNER", "ORG_ADMIN", "MANAGER"].includes(activeOrg.role);
  const canEdit = activeOrg?.role !== "CLIENT";

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

  const refreshUserAndProjects = async (chosenOrg?: string) => {
    setError("");
    try {
      setUser(await api.getMe());
      const orgs = await api.listMyOrganizations();
      setOrganizations(orgs);
      if (!orgs.length) throw new Error("No organization is available for this account.");
      const activeId = chosenOrg || (orgs.some(o => o.id === api.getOrgId()) ? api.getOrgId()! : orgs[0].id);
      api.setOrg(activeId);
      const spaces = await api.listWorkspaces(activeId);
      setWorkspaces(spaces);
      const allProjects = (await Promise.all(spaces.map(ws => api.listWorkspaceProjects(ws.id)))).flat();
      setProjects(allProjects);
      setCurrentProject(previous => allProjects.find(p => p.id === previous?.id) || allProjects[0] || null);
      setMembers(await api.listMembers(activeId));
    } catch (e) { setError((e as Error).message); }
    finally { setInitializing(false); }
  };

  const switchOrganization = async (id: string) => {
    api.setOrg(id); setCurrentProject(null); setSelectedTask(null); setActiveTimer(null);
    setKanbanBoard(null); setGanttChart(null); setProjects([]); setInitializing(true);
    await refreshUserAndProjects(id); await refreshActiveTimer();
  };

  const openTask = async (task: Task) => {
    try { setSelectedTask(await api.getTask(task.id)); }
    catch (e) { setError((e as Error).message); }
  };

  const refreshActiveTimer = async () => {
    try {
      const timer = await api.getActiveTimer();
      setActiveTimer(timer);
      setRevision(v => v + 1);
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
  const { broadcast, connected } = useRealtime(roomName, () => {
    refreshCurrentView(); refreshActiveTimer(); setRevision(v => v + 1);
    if (selectedTask) api.getTask(selectedTask.id).then(fresh => setSelectedTask(current => current?.id === fresh.id ? fresh : current)).catch(() => setSelectedTask(null));
  });

  // Apply a local mutation, refresh our view, and notify other clients in the room.
  const notifyChange = () => {
    refreshCurrentView(); setRevision(v => v + 1);
    if(currentProject) api.getProject(currentProject.id).then(fresh => {
      setCurrentProject(fresh); setProjects(previous => previous.map(p => p.id === fresh.id ? fresh : p));
    }).catch(e => setError(e.message));
    broadcast("TASK_UPDATED", {});
  };

  useEffect(() => {
    const expired = () => {setIsAuthenticated(false); setSelectedTask(null); setCurrentProject(null); setUser(null);};
    window.addEventListener("stride-auth-required", expired);
    return () => window.removeEventListener("stride-auth-required", expired);
  }, []);

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
      setCreating(true);
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
      setError(e.message || "Failed to create task");
    } finally { setCreating(false); }
  };

  if (!isAuthenticated) {
    return <AuthPage onSuccess={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 overflow-hidden text-slate-100 font-sans">
      {/* Top Navigation */}
      <Navbar
        canUseAI={canManage}
        organizations={organizations}
        activeOrgId={api.getOrgId()}
        onSelectOrganization={switchOrganization}
        connected={connected}
        currentProject={currentProject}
        projects={projects}
        onSelectProject={p => {setSelectedTask(null); setKanbanBoard(null); setGanttChart(null); setCurrentProject(p);}}
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
          onOpenCreateTask={() => currentProject ? setIsCreateTaskOpen(true) : setCurrentTab("settings")}
        />

        {/* Dynamic Center View */}
        <main className="flex-1 min-w-0 flex flex-col overflow-hidden">
          {error && <div role="alert" className="error m-4 flex justify-between gap-3"><span>{error}</span><button className="underline" onClick={() => refreshUserAndProjects()}>Retry</button></div>}
          {initializing && <p className="p-6 text-slate-400">Loading workspace…</p>}
          {!initializing && !currentProject && currentTab !== "settings" && <div className="m-auto p-8 text-center space-y-3"><h1 className="text-xl font-semibold">Your next project starts here</h1><p className="text-slate-400">Create a project to organize your team’s work.</p><button className="btn-primary" onClick={() => setCurrentTab("settings")}>Open workspace settings</button></div>}
          {currentTab === "settings" && <SettingsPage org={activeOrg} project={currentProject} workspaces={workspaces} canManage={canManage} onRefresh={() => refreshUserAndProjects()} />}
          {currentProject && currentTab === "table" && <TablePage key={currentProject.id} project={currentProject} onSelectTask={openTask} revision={revision} canEdit={canEdit} />}
          {currentProject && currentTab === "kanban" && (
            <KanbanPage
              canManage={canManage}
              canEdit={canEdit}
              project={currentProject}
              board={kanbanBoard}
              onSelectTask={openTask}
              onRefresh={notifyChange}
            />
          )}

          {currentProject && currentTab === "calendar" && (
            <CalendarPage key={`${currentProject.id}-${revision}`} project={currentProject} onSelectTask={async id => {try {setSelectedTask(await api.getTask(id));} catch(e) {setError((e as Error).message);}}} />
          )}

          {currentProject && currentTab === "gantt" && (
            <GanttPage project={currentProject} gantt={ganttChart} onSelectTask={async id => {try {setSelectedTask(await api.getTask(id));} catch(e) {setError((e as Error).message);}}} />
          )}

          {currentProject && currentTab === "timesheets" && (
            <TimesheetsPage key={currentProject.id} project={currentProject} canReview={canManage} userId={user?.id} externalRevision={revision} />
          )}
        </main>
      </div>

      {/* Task Details Drawer */}
      {selectedTask && currentProject && (
        <TaskDrawer
          task={selectedTask}
          project={currentProject}
          members={members}
          canEdit={canEdit}
          canDelete={canManage}
          statuses={currentProject.statuses || []}
          onClose={() => setSelectedTask(null)}
          onUpdate={() => {
            notifyChange();
            if (selectedTask) {
              api.getTask(selectedTask.id).then(fresh => setSelectedTask(current => current?.id === fresh.id ? fresh : current)).catch(console.error);
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
                disabled={creating}
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
