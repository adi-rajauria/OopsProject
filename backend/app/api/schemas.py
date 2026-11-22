"""Pydantic request/response models (input validation at the HTTP boundary).

Report/intelligence endpoints return the services' frozen dataclasses directly;
FastAPI serialises them, so there is no duplicate model to keep in sync.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AdminLevel, Priority, Role
from app.domain.users import Administrator, Technician, User


class ApiModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


# --- auth / users ----------------------------------------------------------------------------


class RegisterRequest(ApiModel):
    # Format is validated once, in the domain (require_email); EmailStr would reject demo domains like .test
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=30)
    department: str | None = Field(default=None, max_length=80)


class LoginRequest(ApiModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class TechnicianProfileOut(ApiModel):
    skills: list[str]
    experience_years: int
    max_workload: int
    is_available: bool
    is_team_lead: bool
    team: str


class UserOut(ApiModel):
    id: int
    email: str
    full_name: str
    role: str
    code: str
    phone: str | None
    department: str | None
    is_active: bool
    created_at: datetime
    admin_level: str | None = None
    technician_profile: TechnicianProfileOut | None = None

    @classmethod
    def from_domain(cls, user: User) -> "UserOut":
        profile = None
        if isinstance(user, Technician):
            p = user.profile
            profile = TechnicianProfileOut(
                skills=sorted(p.skills),
                experience_years=p.experience_years,
                max_workload=p.max_workload,
                is_available=p.is_available,
                is_team_lead=p.is_team_lead,
                team=p.team,
            )
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            code=user.display_code,
            phone=user.phone,
            department=user.department,
            is_active=user.is_active,
            created_at=user.created_at,
            admin_level=user.admin_level.value if isinstance(user, Administrator) else None,
            technician_profile=profile,
        )


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TechnicianProfileIn(ApiModel):
    skills: list[str] = []
    experience_years: int = Field(default=0, ge=0, le=60)
    max_workload: int = Field(default=8, ge=1, le=50)
    is_available: bool = True
    is_team_lead: bool = False
    team: str = Field(default="General", min_length=1, max_length=60)


class TechnicianProfileUpdate(ApiModel):
    skills: list[str] | None = None
    experience_years: int | None = Field(default=None, ge=0, le=60)
    max_workload: int | None = Field(default=None, ge=1, le=50)
    is_available: bool | None = None
    is_team_lead: bool | None = None
    team: str | None = Field(default=None, min_length=1, max_length=60)


class UserCreate(RegisterRequest):
    role: Role
    admin_level: AdminLevel | None = None
    technician: TechnicianProfileIn | None = None


class UserUpdate(ApiModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    department: str | None = Field(default=None, max_length=80)
    admin_level: AdminLevel | None = None


class AvailabilityIn(ApiModel):
    available: bool


# --- reference data ------------------------------------------------------------------------


class ServiceOut(ApiModel):
    id: int
    code: str
    name: str
    description: str
    business_criticality: int
    owner_team: str
    is_active: bool
    depends_on: list[int]


class ServiceIn(ApiModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=100)
    business_criticality: int = Field(ge=1, le=4)
    owner_team: str = Field(default="General", min_length=1, max_length=60)
    description: str = Field(default="", max_length=1000)


class ServiceUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    business_criticality: int | None = Field(default=None, ge=1, le=4)
    owner_team: str | None = Field(default=None, min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class DependenciesIn(ApiModel):
    depends_on: list[int] = Field(default=[], max_length=50)


class CategoryOut(ApiModel):
    id: int
    code: str
    name: str
    keywords: list[str]
    is_active: bool


class CategoryIn(ApiModel):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=60)
    keywords: list[str] = Field(default=[], max_length=100)


class CategoryUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=2, max_length=60)
    keywords: list[str] | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class PolicyOut(ApiModel):
    id: int
    priority: Priority
    service_id: int | None
    response_minutes: int
    resolution_minutes: int
    warning_threshold_pct: int


class PolicyIn(ApiModel):
    priority: Priority
    service_id: int | None = None
    response_minutes: int = Field(ge=1, le=100_000)
    resolution_minutes: int = Field(ge=1, le=100_000)
    warning_threshold_pct: int = Field(default=75, ge=1, le=99)


class PolicyUpdate(ApiModel):
    response_minutes: int = Field(ge=1, le=100_000)
    resolution_minutes: int = Field(ge=1, le=100_000)
    warning_threshold_pct: int = Field(default=75, ge=1, le=99)


class StrategyIn(ApiModel):
    key: str = Field(min_length=1, max_length=40)


class EscalationSettings(ApiModel):
    include_p2: bool


# --- incidents ------------------------------------------------------------------------------


class IncidentCreate(ApiModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    service_id: int
    impact: int = Field(ge=1, le=4)
    urgency: int = Field(ge=1, le=4)
    affected_users: int = Field(default=1, ge=1, le=100_000)
    category_id: int | None = None
    force: bool = False


class IncidentUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=5000)
    impact: int | None = Field(default=None, ge=1, le=4)
    urgency: int | None = Field(default=None, ge=1, le=4)
    affected_users: int | None = Field(default=None, ge=1, le=100_000)
    category_id: int | None = None


class TextPreview(ApiModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    service_id: int | None = None


class SelfHelpTip(ApiModel):
    """A past fix shown to a reporter; no incident id or number, since employees cannot open others' incidents."""

    title: str
    resolution: str
    similarity: float


class AssignRequest(ApiModel):
    technician_id: int


class QuestionRequest(ApiModel):
    question: str = Field(min_length=3, max_length=5000)


class AnswerRequest(ApiModel):
    answer: str = Field(min_length=3, max_length=5000)


class CommentRequest(ApiModel):
    body: str = Field(min_length=2, max_length=5000)
    internal: bool = False


class ResolveRequest(ApiModel):
    summary: str = Field(min_length=10, max_length=5000)


class ReopenRequest(ApiModel):
    reason: str = Field(min_length=3, max_length=5000)


class VerifyRequest(ApiModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class CloseRequest(ApiModel):
    notes: str | None = Field(default=None, max_length=2000)


class FeedbackRequest(ApiModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class Ref(ApiModel):
    id: int
    name: str
    code: str


class SLAOut(ApiModel):
    response_minutes: int
    resolution_minutes: int
    warning_pct: int
    response_due_at: datetime
    resolution_due_at: datetime
    responded_at: datetime | None
    resolved_at: datetime | None
    response_breached: bool
    resolution_breached: bool
    paused: bool
    paused_seconds: int
    active_target: str | None
    elapsed_pct: float | None
    status: str


class CommentOut(ApiModel):
    id: int | None
    author: Ref | None
    kind: str
    body: str
    is_internal: bool
    created_at: datetime


class LinkOut(ApiModel):
    incident_id: int
    number: str
    title: str
    status: str
    similarity: float
    link_type: str


class FeedbackOut(ApiModel):
    rating: int
    comment: str
    created_at: datetime


class IncidentSummaryOut(ApiModel):
    id: int
    number: str
    title: str
    status: str
    priority: str | None
    priority_score: float | None
    impact: int
    urgency: int
    affected_users: int
    service: Ref | None
    category: Ref | None
    reporter: Ref | None
    technician: Ref | None
    sla_status: str | None
    response_due_at: datetime | None
    resolution_due_at: datetime | None
    escalation_level: int
    created_at: datetime
    updated_at: datetime


class IncidentDetailOut(IncidentSummaryOut):
    description: str
    suggested_category: Ref | None
    sla: SLAOut | None
    comments: list[CommentOut]
    resolution_summary: str | None
    closure_notes: str | None
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    verified_at: datetime | None
    closed_at: datetime | None
    parent_incident: Ref | None
    links: list[LinkOut]
    feedback: FeedbackOut | None
    available_actions: list[str]


class SearchPageOut(ApiModel):
    items: list[IncidentSummaryOut]
    total: int
    page: int
    page_size: int
    pages: int


class AuditRecordOut(ApiModel):
    id: int | None
    created_at: datetime
    actor_id: int | None
    actor_name: str
    action: str
    incident_id: int | None
    incident_number: str | None
    previous_state: str | None
    new_state: str | None
    description: str


class NotificationOut(ApiModel):
    id: int
    channel: str
    type: str
    title: str
    body: str
    incident_id: int | None
    incident_number: str | None
    is_read: bool
    delivered: bool
    delivery_error: str | None
    recipient_id: int
    created_at: datetime


class CountOut(ApiModel):
    count: int
