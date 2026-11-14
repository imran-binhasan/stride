export type OrgRole = 'ORG_OWNER' | 'ORG_ADMIN' | 'MANAGER' | 'MEMBER' | 'CLIENT';
export type TaskPriority = 'URGENT' | 'HIGH' | 'MEDIUM' | 'LOW';
export type DependencyType = 'BLOCKS' | 'BLOCKED_BY' | 'RELATES_TO';
export type StatusCategory = 'BACKLOG' | 'TODO' | 'IN_PROGRESS' | 'IN_REVIEW' | 'DONE';

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string | null;
  is_active: boolean;
  is_superadmin: boolean;
  created_at: string;
}

export interface MyOrg {
  id: string;
  name: string;
  slug: string;
  subscription_tier: string;
  role: OrgRole;
  created_at: string;
}

export interface Workspace {
  id: string;
  org_id: string;
  name: string;
  slug: string;
  description?: string | null;
  created_at: string;
}

export interface WorkflowStatus {
  id: string;
  name: string;
  category: StatusCategory;
  color: string;
  position: number;
  wip_limit?: number | null;
}

export interface CustomFieldDefinition {key:string;name:string;type:'TEXT'|'NUMBER'|'DROPDOWN'|'DATE'|'FORMULA'|'USERS';options?:string[];formula?:string|null;}
export interface Project {
  custom_field_definitions?: CustomFieldDefinition[];
  id: string;
  org_id: string;
  workspace_id: string;
  key: string;
  name: string;
  description?: string | null;
  default_view: string;
  task_counter: number;
  created_at: string;
  statuses: WorkflowStatus[];
  sprints?: Sprint[];
}

export interface Subtask {
  id: string;
  task_id: string;
  title: string;
  is_completed: boolean;
  position: number;
  created_at: string;
}

export interface TaskDependency {
  id: string;
  predecessor_id: string;
  successor_id: string;
  dependency_type: DependencyType;
  lag_days: number;
  created_at: string;
}

export interface RecurrenceRule { frequency: "DAILY" | "WEEKLY" | "MONTHLY" | "CRON"; interval?: number; weekdays?: number[]; until?: string | null; cron?: string | null; }

export interface Task {
  type?: "TASK"|"BUG"|"STORY"|"EPIC"|"MILESTONE";
  recurrence?: RecurrenceRule | null;
  id: string;
  org_id: string;
  project_id: string;
  sprint_id?: string | null;
  status_id: string;
  short_id: string;
  title: string;
  description?: string | null;
  priority: TaskPriority;
  story_points?: number | null;
  estimated_hours?: number | null;
  start_date?: string | null;
  due_date?: string | null;
  position: number;
  custom_fields: Record<string, any>;
  creator_id: string;
  assignee_id?: string | null;
  created_at: string;
  updated_at: string;
  status?: WorkflowStatus;
  assignee?: UserProfile | null;
  subtasks: Subtask[];
  children?: Subtask[];
  comments?: TaskComment[];
  attachments?: Attachment[];
  dependencies_out: TaskDependency[];
  dependencies_in: TaskDependency[];
}

export interface KanbanColumn {
  status: WorkflowStatus;
  wip_exceeded?: boolean;
  task_count: number;
  tasks: Task[];
}

export interface KanbanBoard {
  project_id: string;
  total_tasks: number;
  columns: KanbanColumn[];
}

export interface CalendarTaskItem {
  id: string;
  short_id: string;
  title: string;
  status_name: string;
  status_color: string;
  due_date: string;
  assignee_name?: string | null;
}

export interface CalendarView {
  project_id: string;
  month?: number | null;
  year?: number | null;
  events: CalendarTaskItem[];
}

export interface GanttNode {
  parent_task_id?:string|null;
  is_milestone?:boolean;
  id: string;
  short_id: string;
  title: string;
  duration_days: number;
  early_start: number;
  early_finish: number;
  late_start: number;
  late_finish: number;
  total_float: number;
  is_critical: boolean;
  dependencies_out: string[];
}

export interface GanttChart {
  start_date?:string|null;
  project_id: string;
  project_duration_days: number;
  critical_path: string[];
  nodes: GanttNode[];
}

export interface TenMinuteBlockSummary {
  block_start: string;
  block_end: string;
  activity_percent: number;
  is_idle: boolean;
  keystroke_count: number;
  mouse_distance_px: number;
  screenshot_url?: string | null;
  screenshot_thumbnail?: string | null;
}

export interface DailyActivitySummary {
  user_id: string;
  date: string;
  day_first_start_time?: string | null;
  day_last_end_time?: string | null;
  total_screen_time_seconds: number;
  total_work_seconds: number;
  total_idle_seconds: number;
  overall_day_activity_percent: number;
  total_sessions_count: number;
  total_screenshots_count: number;
  ten_minute_blocks: TenMinuteBlockSummary[];
}

export interface ActiveTimer {
  id: string;
  task_id: string;
  start_time: string;
  end_time?: string | null;
  total_seconds: number;
  is_billable: boolean;
  notes?: string | null;
}

export interface FigmaLink {
  id: string;
  task_id: string;
  figma_url: string;
  file_key: string;
  node_id?: string | null;
  file_name?: string | null;
  thumbnail_url?: string | null;
}

export interface Gate1Response {
  passed: boolean;
  feature_title: string;
  summary: string;
  suggested_priority: TaskPriority;
  estimated_points: number;
  acceptance_criteria: string[];
  ambiguity_score: number;
}

export interface Gate2Response {
  passed: boolean;
  tenant_id: string;
  project_key: string;
  active_workflow_statuses: string[];
  context_token_estimate: number;
  context_payload: Record<string, any>;
}

export interface PlannedTaskNode {
  step_number: number;
  title: string;
  layer: string;
  dependencies: number[];
}

export interface Gate3Response {
  passed: boolean;
  plan_dag: PlannedTaskNode[];
  is_acyclic: boolean;
  risk_assessment: string;
}

export interface Gate4Response {
  passed: boolean;
  generated_test_module: string;
  test_function_names: string[];
  assertions_count: number;
}

export interface Gate5Response {
  passed: boolean;
  static_analysis_passed: boolean;
  tests_executed: number;
  tests_passed: number;
  coverage_percent: number | null;
  execution_status?: string;
  summary: string;
}

export interface FullAIPipelineResponse {
  pipeline_success: boolean;
  gate1_intent: Gate1Response;
  gate2_context: Gate2Response;
  gate3_plan: Gate3Response;
  gate4_tdd: Gate4Response;
  gate5_execution: Gate5Response;
}


export interface Sprint {
  id: string; project_id: string; name: string; goal?: string | null;
  start_date?: string | null; end_date?: string | null;
  status: 'PLANNED' | 'ACTIVE' | 'COMPLETED';
}
export interface OrgMember {
  id: string; org_id: string; email: string; role: OrgRole;
  status: 'PENDING' | 'ACTIVE' | 'SUSPENDED' | 'REMOVED'; user?: UserProfile | null;
}
export interface TaskComment { id: string; content: string; author_id: string; author?: UserProfile; created_at: string; is_internal: boolean }
export interface Attachment { id: string; file_name: string; file_size: number; mime_type: string }
export interface ChecklistItem { id: string; title: string; is_completed: boolean; position: number }
export interface TimeEntry extends ActiveTimer {
  org_id: string; user_id: string; idle_seconds: number; activity_percent: number;
  status: 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED';
}
export interface TableResult { items: Task[]; total: number; limit: number; offset: number }
