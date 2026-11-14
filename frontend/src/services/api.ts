import {
  ActiveTimer,
  OrgMember,
  Sprint,
  TimeEntry,
  ChecklistItem,
  TaskComment,
  Attachment,
  TableResult,
  OrgRole,
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
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
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
    const base = new URL(API_BASE, window.location.origin);
    base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
    base.pathname = base.pathname.replace(/\/$/, "") + "/ws/realtime";
    base.searchParams.set("token", this.token);
    if (this.orgId) base.searchParams.set("org_id", this.orgId);
    return base.toString();
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
          this.setAuth(data.access_token, data.refresh_token, this.orgId ?? undefined);
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
      window.dispatchEvent(new Event("stride-auth-required"));
    }

    if (!res.ok) {
      let errorMsg = `HTTP Error ${res.status}`;
      try {
        const errJson = await res.json();
        errorMsg = Array.isArray(errJson.details) ? errJson.details.map((item: {loc?: string[]; msg?: string}) => `${item.loc?.slice(1).join('.') || 'Input'}: ${item.msg || 'Invalid value'}`).join('; ') : typeof errJson.error === "string" ? errJson.error : typeof errJson.detail === "string" ? errJson.detail : errorMsg;
      } catch {}
      throw new Error(errorMsg);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  }

  async acceptInvite(token: string, full_name: string, password: string) {
    return this.request<{access_token: string; refresh_token: string}>("/organizations/invites/accept", {method:"POST",body:JSON.stringify({token,full_name,password})});
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

  async listMembers(orgId: string): Promise<OrgMember[]> { return this.request(`/organizations/${orgId}/members`); }
  async inviteMember(orgId: string, email: string, role: OrgRole) { return this.request<OrgMember & { invite_token: string }>(`/organizations/${orgId}/members/invite`, { method: "POST", body: JSON.stringify({ email, role }) }); }
  async addMember(orgId: string, email: string, role: OrgRole) { return this.request<OrgMember>(`/organizations/${orgId}/members`, { method: "POST", body: JSON.stringify({ email, role }) }); }
  async updateMember(orgId: string, id: string, changes: Partial<OrgMember>) { return this.request<OrgMember>(`/organizations/${orgId}/members/${id}`, { method: "PATCH", body: JSON.stringify(changes) }); }
  async createWorkspace(orgId: string, name: string) { return this.request<Workspace>(`/organizations/${orgId}/workspaces`, { method: "POST", body: JSON.stringify({ name }) }); }
  async createSprint(projectId: string, values: { name: string; start_date?: string; end_date?: string; goal?: string }) { return this.request<Sprint>(`/projects/${projectId}/sprints`, { method: "POST", body: JSON.stringify(values) }); }
  async updateSprint(id: string, changes: Partial<Sprint>) { return this.request<Sprint>(`/projects/sprints/${id}`, { method: "PATCH", body: JSON.stringify(changes) }); }
  async updateStatus(projectId: string, id: string, changes: Partial<WorkflowStatus>) { return this.request<WorkflowStatus>(`/projects/${projectId}/statuses/${id}`, { method: "PATCH", body: JSON.stringify(changes) }); }
  async deleteTask(id: string) { return this.request<void>(`/tasks/${id}`, { method: "DELETE" }); }
  async addComment(id: string, content: string) { return this.request<TaskComment>(`/tasks/${id}/comments`, { method: "POST", body: JSON.stringify({ content }) }); }
  async getChecklist(id: string) { return this.request<ChecklistItem[]>(`/tasks/${id}/checklist`); }
  async addChecklist(id: string, title: string) { return this.request<ChecklistItem>(`/tasks/${id}/checklist`, { method: "POST", body: JSON.stringify({ title }) }); }
  async updateChecklist(id: string, itemId: string, is_completed: boolean) { return this.request<ChecklistItem>(`/tasks/${id}/checklist/${itemId}`, { method: "PATCH", body: JSON.stringify({ is_completed }) }); }
  async addDependency(id: string, successor_id: string) { return this.request(`/tasks/${id}/dependencies`, { method: "POST", body: JSON.stringify({ successor_id }) }); }
  async removeDependency(id: string, dependencyId: string) { return this.request<void>(`/tasks/${id}/dependencies/${dependencyId}`, { method: "DELETE" }); }
  async getTable(projectId: string, params: Record<string, string> = {}) { return this.request<TableResult>(`/views/table/${projectId}?${new URLSearchParams(params)}`); }
  async calendarExport(projectId: string) {
    const res = await fetch(`${API_BASE}/views/calendar/${projectId}/export.ics`, { headers: { Authorization: `Bearer ${this.token}`, "X-Org-ID": this.orgId || "" } });
    if (!res.ok) throw new Error("Calendar export failed");
    return res.blob();
  }
  async uploadAttachment(taskId: string, file: File): Promise<Attachment> {
    const reservation = await this.request<{attachment_id: string; upload_url: string}>(`/tasks/${taskId}/attachments/upload-url`, { method: "POST", body: JSON.stringify({ file_name: file.name, file_size: file.size, mime_type: file.type || "application/octet-stream" }) });
    const uploaded = await fetch(reservation.upload_url, { method: "PUT", headers: { "Content-Type": file.type || "application/octet-stream" }, body: file });
    if (!uploaded.ok) throw new Error("File upload failed");
    return this.request<Attachment>(`/tasks/${taskId}/attachments/confirm`, { method: "POST", body: JSON.stringify({ attachment_id: reservation.attachment_id }) });
  }
  async attachmentUrl(taskId: string, id: string) { return this.request<{download_url: string}>(`/tasks/${taskId}/attachments/${id}/download-url`); }
  async listTimeEntries(allMembers = false, offset = 0) { return this.request<TimeEntry[]>(`/time-tracking/entries?limit=50&offset=${offset}&all_members=${allMembers}`); }
  async manualTimeEntry(values: {task_id: string; start_time: string; end_time: string; notes?: string; is_billable: boolean}) { return this.request<TimeEntry>("/time-tracking/entries", { method: "POST", body: JSON.stringify(values) }); }
  async timeEntryAction(id: string, action: "submit" | "recall" | "review", values?: { status: string; reason?: string }) { return this.request<TimeEntry>(`/time-tracking/entries/${id}/${action}`, { method: "POST", body: JSON.stringify(values || {}) }); }
  async deleteTimeEntry(id: string) { return this.request<void>(`/time-tracking/entries/${id}`, { method: "DELETE" }); }
  async connectGithub(projectId: string, repo_owner: string, repo_name: string) { return this.request(`/integrations/projects/${projectId}/github`, { method: "POST", body: JSON.stringify({repo_owner, repo_name}) }); }

  // AI Pipeline
  async runFullAIPipeline(projectId: string, featurePrompt: string): Promise<FullAIPipelineResponse> {
    return this.request<FullAIPipelineResponse>("/ai/pipeline/run-all", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, feature_prompt: featurePrompt }),
    });
  }
}

export const api = new ApiClient();
