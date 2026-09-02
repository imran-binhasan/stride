import {
  ActiveTimer,
  CalendarView,
  DailyActivitySummary,
  FigmaLink,
  FullAIPipelineResponse,
  GanttChart,
  KanbanBoard,
  MyOrg,
  Project,
  Task,
  UserProfile,
  WorkflowStatus,
  Workspace,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE || "/api/v1";

function decodeOrgIdFromToken(token: string): string | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.org_id ?? null;
  } catch {
    return null;
  }
}

class ApiClient {
  private token: string | null = localStorage.getItem("stride_token");
  private refreshToken: string | null = localStorage.getItem("stride_refresh");
  private orgId: string | null = localStorage.getItem("stride_org_id");
  private refreshing: Promise<boolean> | null = null;

  setAuth(token: string, refreshToken?: string, orgId?: string) {
    this.token = token;
    localStorage.setItem("stride_token", token);
    if (refreshToken) {
      this.refreshToken = refreshToken;
      localStorage.setItem("stride_refresh", refreshToken);
    }
    // The org id is carried as a JWT claim, so it's always available post-login.
    const resolvedOrg = orgId ?? decodeOrgIdFromToken(token);
    if (resolvedOrg) {
      this.orgId = resolvedOrg;
      localStorage.setItem("stride_org_id", resolvedOrg);
    }
  }

  setOrg(orgId: string) {
    this.orgId = orgId;
    localStorage.setItem("stride_org_id", orgId);
  }

  clearAuth() {
    this.token = null;
    this.refreshToken = null;
    this.orgId = null;
    localStorage.removeItem("stride_token");
    localStorage.removeItem("stride_refresh");
    localStorage.removeItem("stride_org_id");
  }

  getToken(): string | null {
    return this.token;
  }

  getOrgId(): string | null {
    return this.orgId;
  }

  /** WebSocket URL for the realtime endpoint, carrying the access token. */
  realtimeUrl(): string | null {
    if (!this.token) return null;
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/ws/realtime?token=${encodeURIComponent(this.token)}`;
  }

  private async doRefresh(): Promise<boolean> {
    if (!this.refreshToken) return false;
    // Collapse concurrent refreshes into one in-flight request.
    if (!this.refreshing) {
      this.refreshing = (async () => {
        try {
          const res = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: this.refreshToken }),
          });
          if (!res.ok) return false;
          const data = (await res.json()) as { access_token: string; refresh_token: string };
          this.setAuth(data.access_token, data.refresh_token);
          return true;
        } catch {
          return false;
        } finally {
          this.refreshing = null;
        }
      })();
    }
    return this.refreshing;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retry = true
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }
    if (this.orgId) {
      headers["X-Org-ID"] = this.orgId;
    }

    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (res.status === 401 && retry && this.refreshToken) {
      // Access token likely expired — rotate once and retry transparently.
      const refreshed = await this.doRefresh();
      if (refreshed) {
        return this.request<T>(endpoint, options, false);
      }
      this.clearAuth();
    }

    if (!res.ok) {
      let errorMsg = `HTTP Error ${res.status}`;
      try {
        const errJson = await res.json();
        errorMsg = errJson.error || errJson.detail || errorMsg;
      } catch {}
      throw new Error(errorMsg);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  }

  // Auth
  async login(payload: { email: string; password: string }) {
    return this.request<{ access_token: string; refresh_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async register(payload: { email: string; password: string; full_name: string; organization_name?: string }) {
    return this.request<{ success: boolean; data: { user: UserProfile; tokens: { access_token: string; refresh_token: string } } }>(
      "/auth/register",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  }

  async logout(): Promise<void> {
    if (this.refreshToken) {
      try {
        await this.request("/auth/logout", {
          method: "POST",
          body: JSON.stringify({ refresh_token: this.refreshToken }),
        });
      } catch {
        // best-effort; clear locally regardless
      }
    }
    this.clearAuth();
  }

  async getMe(): Promise<UserProfile> {
    return this.request<UserProfile>("/auth/me");
  }

  // Organizations & Workspaces
  async listMyOrganizations(): Promise<MyOrg[]> {
    return this.request<MyOrg[]>("/organizations");
  }

  async listWorkspaces(orgId: string): Promise<Workspace[]> {
    return this.request<Workspace[]>(`/organizations/${orgId}/workspaces`);
  }

  // Projects
  async getProject(projectId: string): Promise<Project> {
    return this.request<Project>(`/projects/${projectId}`);
  }

  async listWorkspaceProjects(workspaceId: string): Promise<Project[]> {
    return this.request<Project[]>(`/projects/workspace/${workspaceId}`);
  }

  async createProject(payload: { workspace_id: string; name: string; key: string; description?: string }): Promise<Project> {
    return this.request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async addCustomStatus(projectId: string, payload: { name: string; color: string; category: string; position: number }): Promise<WorkflowStatus> {
    return this.request<WorkflowStatus>(`/projects/${projectId}/statuses`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // Tasks
  async getTask(taskId: string): Promise<Task> {
    return this.request<Task>(`/tasks/${taskId}`);
  }

  async listProjectTasks(projectId: string): Promise<Task[]> {
    return this.request<Task[]>(`/tasks/project/${projectId}`);
  }

  async createTask(payload: {
    project_id: string;
    title: string;
    description?: string;
    status_id?: string;
    priority?: string;
    story_points?: number;
    estimated_hours?: number;
    due_date?: string;
    custom_fields?: Record<string, any>;
  }): Promise<Task> {
    return this.request<Task>("/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async moveTask(taskId: string, statusId: string, newPosition: number): Promise<Task> {
    return this.request<Task>(`/tasks/${taskId}/move`, {
      method: "PATCH",
      body: JSON.stringify({ status_id: statusId, new_position: newPosition }),
    });
  }

  async updateTask(taskId: string, payload: Partial<Task>): Promise<Task> {
    return this.request<Task>(`/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async addSubtask(taskId: string, title: string): Promise<any> {
    return this.request(`/tasks/${taskId}/subtasks`, {
      method: "POST",
      body: JSON.stringify({ title, position: 0 }),
    });
  }

  // Views
  async getKanban(projectId: string, sprintId?: string): Promise<KanbanBoard> {
    const q = sprintId ? `?sprint_id=${sprintId}` : "";
    return this.request<KanbanBoard>(`/views/kanban/${projectId}${q}`);
  }

  async getCalendar(projectId: string, month?: number, year?: number): Promise<CalendarView> {
    const params = new URLSearchParams();
    if (month) params.append("month", month.toString());
    if (year) params.append("year", year.toString());
    const q = params.toString() ? `?${params.toString()}` : "";
    return this.request<CalendarView>(`/views/calendar/${projectId}${q}`);
  }

  async getGantt(projectId: string): Promise<GanttChart> {
    return this.request<GanttChart>(`/views/gantt/${projectId}`);
  }

  // Time Tracking & Telemetry
  async getActiveTimer(): Promise<ActiveTimer | null> {
    return this.request<ActiveTimer | null>("/time-tracking/timer/active");
  }

  async startTimer(taskId: string, isBillable = true, notes?: string): Promise<ActiveTimer> {
    return this.request<ActiveTimer>("/time-tracking/timer/start", {
      method: "POST",
      body: JSON.stringify({ task_id: taskId, is_billable: isBillable, notes }),
    });
  }

  async stopTimer(notes?: string): Promise<ActiveTimer> {
    return this.request<ActiveTimer>("/time-tracking/timer/stop", {
      method: "POST",
      body: JSON.stringify({ notes }),
    });
  }

  async getDailyReport(dateStr?: string, userId?: string): Promise<DailyActivitySummary> {
    const params = new URLSearchParams();
    if (dateStr) params.append("date", dateStr);
    if (userId) params.append("user_id", userId);
    const q = params.toString() ? `?${params.toString()}` : "";
    return this.request<DailyActivitySummary>(`/time-tracking/reports/daily${q}`);
  }

  // Figma & Integrations
  async attachFigma(taskId: string, figmaUrl: string, fileName?: string): Promise<FigmaLink> {
    return this.request<FigmaLink>(`/integrations/tasks/${taskId}/figma`, {
      method: "POST",
      body: JSON.stringify({ figma_url: figmaUrl, file_name: fileName }),
    });
  }

  async listFigmaLinks(taskId: string): Promise<FigmaLink[]> {
    return this.request<FigmaLink[]>(`/integrations/tasks/${taskId}/figma`);
  }

  // AI Pipeline
  async runFullAIPipeline(projectId: string, featurePrompt: string): Promise<FullAIPipelineResponse> {
    return this.request<FullAIPipelineResponse>("/ai/pipeline/run-all", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, feature_prompt: featurePrompt }),
    });
  }
}

export const api = new ApiClient();
