export interface EventMsg {
  type?: string;
  ts?: number;
  canonical_type?: string;
  agent_layer?: string;
  actor?: string;
  kind?: string;
  text?: string;
  action_summary?: string;
  title?: string;
  reason?: string;
  status?: string;
  message_id?: string;
  item_id?: string;
  [key: string]: unknown;
}

export interface ProjectRow {
  id: string;
  label: string;
  display_name?: string;
  objective: string;
  cwd?: string;
  workdir?: string;
  launch_cwd?: string;
  last_active: number;
  daemon_alive: boolean;
  daemon_pid: number | null;
  uptime_seconds: number | null;
  active_role?: string;
  activity?: string;
  current_task?: string;
  unfinished_tasks?: number;
  continuous_enabled?: boolean;
  spend_usd?: number | null;
}

export interface ProjectIndex {
  projects: ProjectRow[];
  local_cwd: string;
}

export interface DaemonHealth {
  state?: string;
  stalled?: boolean;
  last_progress_at?: number;
  last_progress_event?: string;
  seconds_since_progress?: number;
}

export interface Daemon {
  alive: boolean;
  pid: number | null;
  control_available?: boolean;
  uptime_seconds: number | null;
  started_at_iso?: string;
  backend: string | null;
  backend_label?: string | null;
  heartbeat_age_seconds?: number | null;
  health?: DaemonHealth;
  runtime?: {
    revision?: string;
    package_version?: string;
    worktree?: { branch?: string; dirty?: boolean; git_available?: boolean };
    [key: string]: unknown;
  } | null;
  [key: string]: unknown;
}

export interface Role {
  role: string;
  backend: string;
  backend_label: string;
  model: string;
  effort: string | null;
  active: boolean;
  label: string;
  status: string;
  age_s: number | null;
}

export interface MissionRoleView {
  role: string;
  status: string;
  label: string;
  updated_at: number;
  backend?: string;
  model?: string;
  effort?: string | null;
}

export interface MissionRoleWorkItem {
  id: string;
  ts: number;
  role: string;
  kind: string;
  title: string;
  detail: string;
  status: string;
  item_id?: string;
  mission_id?: string;
  mission_title?: string;
  round_index?: number | null;
}

export interface MissionDagNode {
  id: string;
  title: string;
  objective: string;
  status: string;
  deps: string[];
  branch_id?: string;
  acceptance_check?: string;
  plan_hypothesis?: string;
  goal_contribution?: string;
  expected_regressions?: string;
  decision_rule?: string;
  non_goals?: string[];
}

export interface MissionTimelineItem {
  id: string;
  ts: number;
  type: string;
  role: string;
  title: string;
  detail: string;
  tone: string;
  item_id?: string;
}

export interface MissionView {
  schema_version: number;
  bootstrapped?: boolean;
  mission: {
    id: string;
    title: string;
    objective: string;
    status: string;
    started_at: number | null;
    completed_at: number | null;
    elapsed_seconds: number;
    campaign_started_at: number | null;
    campaign_elapsed_seconds: number;
  };
  stage: { id: string; label: string };
  round: { current: number; max: number };
  active_role: string;
  roles: MissionRoleView[];
  role_work: MissionRoleWorkItem[];
  dag: MissionDagNode[];
  timeline: MissionTimelineItem[];
  artifacts: Array<Record<string, unknown>>;
  learned_skills: Array<Record<string, unknown>>;
  learned_wiki_pages: Array<Record<string, unknown>>;
  achievement: Record<string, unknown> | null;
  review: { status: string; reason: string; rejected_attempts: number };
  frontier: { change: string; summary: string; updated_at: number };
  outcome: Record<string, unknown>;
  last_event_ts: number;
  updated_at: number;
  metrics?: Record<string, unknown>;
}

export interface BacklogItem {
  id: string;
  title: string;
  objective: string;
  status: string;
  priority: number;
  deps?: string[];
  started_ts?: number | null;
  finished_ts?: number | null;
  last_error?: string;
  acceptance_check?: string;
  plan_hypothesis?: string;
  goal_contribution?: string;
  expected_regressions?: string;
  decision_rule?: string;
  non_goals?: string[];
  outcome?: Record<string, unknown>;
}

export interface UsageSummary {
  call_count: number;
  known_cost_usd: number;
  cost_usd: number | null;
  pricing_status: string;
  input_tokens: number;
  output_tokens: number;
  reasoning_output_tokens: number;
  premium_requests: number;
}

export interface Snapshot {
  schema_version?: number;
  session: {
    id: string;
    display_name: string;
    objective: string;
    created?: number;
    last_active: number;
    cwd: string;
    workdir?: string;
    launch_cwd?: string;
  };
  daemon: Daemon;
  roles: Role[];
  backlog: BacklogItem[];
  recent_events: EventMsg[];
  spend_usd?: number | null;
  spend_status?: string;
  usage_summary?: UsageSummary;
  mission_view?: MissionView | null;
  continuous?: ContinuousState;
  pending_questions?: Array<Record<string, unknown>>;
  daemon_commands?: { revision: number; recent?: Array<Record<string, unknown>> } | null;
  diagnostics?: Array<{ section: string; error_type: string; message: string }>;
}

export interface ContinuousState {
  enabled: boolean;
  objective: string;
  done_reason?: string;
  done_at?: string;
}

export interface StatusView {
  identity: string;
  backlog_pending: BacklogItem[];
  pending_questions: Array<Record<string, unknown>>;
  journal: JournalEntry[];
  continuous: ContinuousState;
  inbox_pending: number;
  daemon: Daemon;
  roles: Role[];
  active_role: string | null;
}

export interface Turn {
  ts: number;
  role: string;
  text: string;
}

export interface JournalEntry {
  id: string;
  ts: number;
  kind: string;
  title: string;
  summary: string;
  tags: string[];
  cost_usd?: number;
  extra?: Record<string, unknown>;
}

export type ArtifactKind =
  | 'text'
  | 'markdown'
  | 'html'
  | 'json'
  | 'table'
  | 'image'
  | 'pdf'
  | 'audio'
  | 'video'
  | 'binary';

export interface ArtifactInfo {
  path: string;
  name: string;
  why: string;
  exists: boolean;
  kind: ArtifactKind;
  mime: string;
  size: number;
  mtime: number | null;
  source?: 'manager_live' | 'reviewer_evidence' | 'research_registered';
  group_title?: string;
  preview?: string;
  truncated?: boolean;
}

export interface GitDiffView {
  available: boolean;
  branch: string;
  status: string;
  stat: string;
  diff: string;
  truncated: boolean;
}

export interface PromptRewrite {
  original: string;
  rewritten: string;
  changes: string[];
  questions: string[];
  error: string;
}

export interface ManagerResult {
  kind?: string;
  reply?: string | null;
  item?: BacklogItem | null;
  daemon_alive?: boolean;
  [key: string]: unknown;
}

export type PageId =
  | 'overview'
  | 'experiments'
  | 'copilot'
  | 'literature'
  | 'inbox'
  | 'ide'
  | 'paper'
  | 'reviewer'
  | 'release';
