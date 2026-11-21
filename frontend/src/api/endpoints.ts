import { http, type Query } from "./client";
import type {
  AuditRecord,
  Category,
  CategorySuggestion,
  Comment,
  CorrelationReport,
  Feedback,
  IncidentDetail,
  IncidentLink,
  IncidentSummary,
  Notification,
  Overview,
  Recommendation,
  Ref,
  ResolutionEstimate,
  RiskAssessment,
  RiskLevel,
  SearchPage,
  SelfHelpTip,
  Service,
  ServiceStats,
  SLACheckSummary,
  SLAPolicy,
  SLAReport,
  StrategyInfo,
  SuggestedResolution,
  TechnicianProfile,
  TechnicianStats,
  TokenResponse,
  TrendPoint,
  User,
  Role,
  AdminLevel,
  Priority,
} from "./types";

export interface NewIncident {
  title: string;
  description: string;
  service_id: number;
  impact: number;
  urgency: number;
  affected_users: number;
  category_id: number | null;
  force?: boolean;
}

export type IncidentPatch = Partial<
  Pick<NewIncident, "title" | "description" | "impact" | "urgency" | "affected_users" | "category_id">
>;

export const authApi = {
  login: (email: string, password: string) => http.post<TokenResponse>("/auth/login", { email, password }),
  register: (body: { email: string; full_name: string; password: string; phone?: string; department?: string }) =>
    http.post<User>("/auth/register", body),
  me: () => http.get<User>("/auth/me"),
};

export const incidentsApi = {
  search: (query: Query) => http.get<SearchPage>("/incidents", query),
  get: (id: number) => http.get<IncidentDetail>(`/incidents/${id}`),
  create: (body: NewIncident) => http.post<IncidentDetail>("/incidents", body),
  update: (id: number, body: IncidentPatch) => http.patch<IncidentDetail>(`/incidents/${id}`, body),
  assign: (id: number, technician_id: number) =>
    http.post<IncidentDetail>(`/incidents/${id}/assign`, { technician_id }),
  autoAssign: (id: number) => http.post<IncidentDetail>(`/incidents/${id}/auto-assign`),
  acknowledge: (id: number) => http.post<IncidentDetail>(`/incidents/${id}/acknowledge`),
  start: (id: number) => http.post<IncidentDetail>(`/incidents/${id}/start`),
  requestInfo: (id: number, question: string) =>
    http.post<IncidentDetail>(`/incidents/${id}/request-info`, { question }),
  provideInfo: (id: number, answer: string) => http.post<IncidentDetail>(`/incidents/${id}/provide-info`, { answer }),
  comment: (id: number, body: string, internal: boolean) =>
    http.post<Comment>(`/incidents/${id}/comments`, { body, internal }),
  resolve: (id: number, summary: string) => http.post<IncidentDetail>(`/incidents/${id}/resolve`, { summary }),
  reopen: (id: number, reason: string) => http.post<IncidentDetail>(`/incidents/${id}/reopen`, { reason }),
  verify: (id: number, rating: number | null, comment: string) =>
    http.post<IncidentDetail>(`/incidents/${id}/verify`, { rating, comment }),
  close: (id: number, notes: string | null) => http.post<IncidentDetail>(`/incidents/${id}/close`, { notes }),
  feedback: (id: number, rating: number, comment: string) =>
    http.post<Feedback>(`/incidents/${id}/feedback`, { rating, comment }),
  audit: (id: number) => http.get<AuditRecord[]>(`/incidents/${id}/audit`),
  recommendations: (id: number) => http.get<Recommendation[]>(`/incidents/${id}/recommendations`),
  suggestedResolutions: (id: number) => http.get<SuggestedResolution[]>(`/incidents/${id}/suggested-resolutions`),
  resolutionEstimate: (id: number) => http.get<ResolutionEstimate | null>(`/incidents/${id}/resolution-estimate`),
};

export const intelligenceApi = {
  suggestCategory: (title: string, description: string) =>
    http.post<CategorySuggestion[]>("/intelligence/suggest-category", { title, description }),
  checkDuplicates: (title: string, description: string, service_id: number) =>
    http.post<IncidentLink[]>("/intelligence/check-duplicates", { title, description, service_id }),
  selfHelp: (title: string, description: string) =>
    http.post<SelfHelpTip[]>("/intelligence/self-help", { title, description }),
  slaRisk: (minimum: RiskLevel = "MEDIUM") => http.get<RiskAssessment[]>("/intelligence/sla-risk", { minimum }),
  correlation: () => http.get<CorrelationReport>("/intelligence/correlation"),
};

export const lookupsApi = {
  services: () => http.get<Service[]>("/lookups/services"),
  categories: () => http.get<Category[]>("/lookups/categories"),
  technicians: () => http.get<Ref[]>("/lookups/technicians"),
};

export const technicianApi = {
  queue: () => http.get<IncidentSummary[]>("/technicians/me/queue"),
  setAvailability: (available: boolean) => http.put<User>("/technicians/me/availability", { available }),
  workload: () => http.get<TechnicianStats[]>("/technicians/workload"),
};

export const notificationsApi = {
  inbox: (unreadOnly = false, limit = 50) =>
    http.get<Notification[]>("/notifications", { unread_only: unreadOnly, limit }),
  unreadCount: () => http.get<{ count: number }>("/notifications/unread-count"),
  markRead: (id: number) => http.post<Notification>(`/notifications/${id}/read`),
  markAllRead: () => http.post<{ count: number }>("/notifications/read-all"),
};

export const reportsApi = {
  overview: () => http.get<Overview>("/reports/overview"),
  technicians: () => http.get<TechnicianStats[]>("/reports/technicians"),
  services: () => http.get<ServiceStats[]>("/reports/services"),
  sla: () => http.get<SLAReport>("/reports/sla"),
  trends: (days = 14) => http.get<TrendPoint[]>("/reports/trends", { days }),
};

export interface NewUser {
  role: Role;
  email: string;
  full_name: string;
  password: string;
  phone?: string | null;
  department?: string | null;
  admin_level?: AdminLevel | null;
  technician?: Partial<TechnicianProfile> | null;
}

export const adminApi = {
  users: (role?: Role) => http.get<User[]>("/admin/users", { role }),
  createUser: (body: NewUser) => http.post<User>("/admin/users", body),
  updateUser: (id: number, body: { full_name?: string; phone?: string; department?: string; admin_level?: AdminLevel }) =>
    http.patch<User>(`/admin/users/${id}`, body),
  setActive: (id: number, active: boolean) =>
    http.post<User>(`/admin/users/${id}/${active ? "activate" : "deactivate"}`),
  updateTechnician: (id: number, body: Partial<TechnicianProfile>) =>
    http.patch<User>(`/admin/technicians/${id}`, body),
  services: () => http.get<Service[]>("/admin/services"),
  createService: (body: {
    code: string;
    name: string;
    business_criticality: number;
    owner_team: string;
    description: string;
  }) => http.post<Service>("/admin/services", body),
  updateService: (id: number, body: Partial<Pick<Service, "name" | "business_criticality" | "owner_team" | "description" | "is_active">>) =>
    http.patch<Service>(`/admin/services/${id}`, body),
  setDependencies: (id: number, depends_on: number[]) =>
    http.put<Service>(`/admin/services/${id}/dependencies`, { depends_on }),
  categories: () => http.get<Category[]>("/admin/categories"),
  createCategory: (body: { code: string; name: string; keywords: string[] }) =>
    http.post<Category>("/admin/categories", body),
  updateCategory: (id: number, body: Partial<Pick<Category, "name" | "keywords" | "is_active">>) =>
    http.patch<Category>(`/admin/categories/${id}`, body),
  policies: () => http.get<SLAPolicy[]>("/admin/sla-policies"),
  createPolicy: (body: {
    priority: Priority;
    service_id: number | null;
    response_minutes: number;
    resolution_minutes: number;
    warning_threshold_pct: number;
  }) => http.post<SLAPolicy>("/admin/sla-policies", body),
  updatePolicy: (id: number, body: { response_minutes: number; resolution_minutes: number; warning_threshold_pct: number }) =>
    http.put<SLAPolicy>(`/admin/sla-policies/${id}`, body),
  deletePolicy: (id: number) => http.delete<void>(`/admin/sla-policies/${id}`),
  strategies: () => http.get<StrategyInfo[]>("/admin/settings/assignment-strategy"),
  setStrategy: (key: string) => http.put<StrategyInfo[]>("/admin/settings/assignment-strategy", { key }),
  escalation: () => http.get<{ include_p2: boolean }>("/admin/settings/escalation"),
  setEscalation: (include_p2: boolean) => http.put<{ include_p2: boolean }>("/admin/settings/escalation", { include_p2 }),
  auditLogs: (query: Query) => http.get<AuditRecord[]>("/admin/audit-logs", query),
  deliveryLog: (limit = 200) => http.get<Notification[]>("/admin/notifications", { limit }),
  checkSlaNow: () => http.post<SLACheckSummary>("/admin/sla/check-now"),
};
