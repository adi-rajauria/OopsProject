// Mirrors the FastAPI response models (backend/app/api/schemas.py and the service dataclasses).

export type Role = "EMPLOYEE" | "TECHNICIAN" | "ADMINISTRATOR";
export type AdminLevel = "SYSTEM_ADMIN" | "IT_MANAGER";
export type IncidentStatus =
  | "NEW"
  | "CLASSIFIED"
  | "ASSIGNED"
  | "ACKNOWLEDGED"
  | "IN_PROGRESS"
  | "PENDING_INFO"
  | "RESOLVED"
  | "VERIFIED"
  | "CLOSED";
export type Priority = "P1" | "P2" | "P3" | "P4";
export type SLAStatus = "ON_TRACK" | "AT_RISK" | "BREACHED" | "PAUSED" | "MET";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "BREACHED";
export type SortOrder = "-created_at" | "created_at" | "priority" | "-updated_at";

export const ALL_STATUSES: IncidentStatus[] = [
  "NEW",
  "CLASSIFIED",
  "ASSIGNED",
  "ACKNOWLEDGED",
  "IN_PROGRESS",
  "PENDING_INFO",
  "RESOLVED",
  "VERIFIED",
  "CLOSED",
];
export const ALL_PRIORITIES: Priority[] = ["P1", "P2", "P3", "P4"];
export const ALL_SLA_STATUSES: SLAStatus[] = ["ON_TRACK", "AT_RISK", "BREACHED", "PAUSED", "MET"];

export interface TechnicianProfile {
  skills: string[];
  experience_years: number;
  max_workload: number;
  is_available: boolean;
  is_team_lead: boolean;
  team: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  code: string;
  phone: string | null;
  department: string | null;
  is_active: boolean;
  created_at: string;
  admin_level: AdminLevel | null;
  technician_profile: TechnicianProfile | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Ref {
  id: number;
  name: string;
  code: string;
}

export interface IncidentSummary {
  id: number;
  number: string;
  title: string;
  status: IncidentStatus;
  priority: Priority | null;
  priority_score: number | null;
  impact: number;
  urgency: number;
  affected_users: number;
  service: Ref | null;
  category: Ref | null;
  reporter: Ref | null;
  technician: Ref | null;
  sla_status: SLAStatus | null;
  response_due_at: string | null;
  resolution_due_at: string | null;
  escalation_level: number;
  created_at: string;
  updated_at: string;
}

export interface SLAInfo {
  response_minutes: number;
  resolution_minutes: number;
  warning_pct: number;
  response_due_at: string;
  resolution_due_at: string;
  responded_at: string | null;
  resolved_at: string | null;
  response_breached: boolean;
  resolution_breached: boolean;
  paused: boolean;
  paused_seconds: number;
  active_target: "RESPONSE" | "RESOLUTION" | null;
  elapsed_pct: number | null;
  status: SLAStatus;
}

export type CommentKind = "COMMENT" | "NOTE" | "INFO_REQUEST" | "INFO_REPLY" | "RESOLUTION";

export interface Comment {
  id: number | null;
  author: Ref | null;
  kind: CommentKind;
  body: string;
  is_internal: boolean;
  created_at: string;
}

export interface IncidentLink {
  incident_id: number;
  number: string;
  title: string;
  status: IncidentStatus;
  similarity: number;
  link_type: "DUPLICATE" | "RELATED";
}

export interface Feedback {
  rating: number;
  comment: string;
  created_at: string;
}

export type IncidentAction =
  | "acknowledge"
  | "start_work"
  | "request_info"
  | "resolve"
  | "provide_info"
  | "verify"
  | "reopen"
  | "assign"
  | "close"
  | "update"
  | "comment"
  | "feedback";

export interface IncidentDetail extends IncidentSummary {
  description: string;
  suggested_category: Ref | null;
  sla: SLAInfo | null;
  comments: Comment[];
  resolution_summary: string | null;
  closure_notes: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  verified_at: string | null;
  closed_at: string | null;
  parent_incident: Ref | null;
  links: IncidentLink[];
  feedback: Feedback | null;
  available_actions: IncidentAction[];
}

export interface SearchPage {
  items: IncidentSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AuditRecord {
  id: number | null;
  created_at: string;
  actor_id: number | null;
  actor_name: string;
  action: string;
  incident_id: number | null;
  incident_number: string | null;
  previous_state: string | null;
  new_state: string | null;
  description: string;
}

export interface Notification {
  id: number;
  channel: "IN_APP" | "EMAIL" | "SMS";
  type: string;
  title: string;
  body: string;
  incident_id: number | null;
  incident_number: string | null;
  is_read: boolean;
  delivered: boolean;
  delivery_error: string | null;
  recipient_id: number;
  created_at: string;
}

export interface Service {
  id: number;
  code: string;
  name: string;
  description: string;
  business_criticality: number;
  owner_team: string;
  is_active: boolean;
  depends_on: number[];
}

export interface Category {
  id: number;
  code: string;
  name: string;
  keywords: string[];
  is_active: boolean;
}

export interface SLAPolicy {
  id: number;
  priority: Priority;
  service_id: number | null;
  response_minutes: number;
  resolution_minutes: number;
  warning_threshold_pct: number;
}

export interface StrategyInfo {
  key: string;
  name: string;
  description: string;
  active: boolean;
}

export interface Overview {
  total: number;
  open: number;
  critical_open: number;
  unassigned: number;
  resolved: number;
  closed: number;
  sla_violations: number;
  breached_open: number;
  at_risk: number;
  mttr_hours: number | null;
  avg_rating: number | null;
  feedback_count: number;
  by_status: Partial<Record<IncidentStatus, number>>;
  by_priority_open: Record<Priority, number>;
}

export interface TechnicianStats {
  technician_id: number;
  name: string;
  code: string;
  team: string;
  is_available: boolean;
  is_team_lead: boolean;
  active: number;
  max_workload: number;
  utilisation_pct: number;
  resolved_total: number;
  avg_resolution_hours: number | null;
  avg_rating: number | null;
}

export interface ServiceStats {
  service_id: number;
  code: string;
  name: string;
  criticality: number;
  total: number;
  open: number;
  violations: number;
  mttr_hours: number | null;
}

export interface ViolationRow {
  incident_id: number;
  number: string;
  title: string;
  priority: Priority | null;
  status: IncidentStatus;
  service: string;
  technician: string | null;
  target: "RESPONSE" | "RESOLUTION";
  due_at: string;
  detected_at: string;
  overdue_minutes: number;
}

export interface ComplianceRow {
  priority: Priority;
  evaluated: number;
  met: number;
  compliance_pct: number | null;
}

export interface SLAReport {
  violations: ViolationRow[];
  compliance: ComplianceRow[];
}

export interface TrendPoint {
  day: string;
  created: number;
  resolved: number;
}

export interface Recommendation {
  technician_id: number;
  name: string;
  score: number;
  eligible: boolean;
  reasons: string[];
  breakdown: Record<string, number>;
}

export interface SuggestedResolution {
  incident_id: number;
  number: string;
  title: string;
  resolution: string;
  similarity: number;
}

export interface SelfHelpTip {
  title: string;
  resolution: string;
  similarity: number;
}

export interface ResolutionEstimate {
  median_minutes: number;
  sample_size: number;
  basis: string;
  expected_by: string | null;
  reason: string;
}

export interface RiskAssessment {
  incident_id: number;
  number: string;
  title: string;
  priority: Priority;
  status: IncidentStatus;
  assigned_technician_id: number | null;
  target: "RESPONSE" | "RESOLUTION";
  due_at: string;
  elapsed_pct: number;
  minutes_left: number;
  risk_score: number;
  level: RiskLevel;
  reasons: string[];
}

export interface ServiceNode {
  service_id: number;
  code: string;
  name: string;
  criticality: number;
  open_incidents: number;
  recent_incidents: number;
  health: "HEALTHY" | "DEGRADED" | "HOTSPOT";
  depends_on: number[];
}

export interface CorrelationFinding {
  kind: "HOTSPOT" | "UPSTREAM_CAUSE";
  root_service_id: number;
  root_service: string;
  incident_ids: number[];
  explanation: string;
}

export interface CorrelationReport {
  nodes: ServiceNode[];
  edges: [number, number][];
  findings: CorrelationFinding[];
}

export interface CategorySuggestion {
  category_id: number;
  code: string;
  name: string;
  confidence: number;
  matched_keywords: string[];
  reason: string;
}

export interface SLACheckSummary {
  checked: number;
  warnings: number;
  violations: number;
  escalations: number;
}

export interface LiveEvent {
  type: "incident";
  action: string;
  incident_id: number;
  number: string;
  title: string;
  status: IncidentStatus;
  priority: Priority | null;
  description: string;
  at: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> };
}
