"""Translate between ORM rows and domain objects (keeps the domain framework-free)."""

from datetime import datetime

from app.domain.audit import AuditRecord
from app.domain.category import Category
from app.domain.clock import ensure_utc
from app.domain.enums import AdminLevel, ChannelType, CommentKind, IncidentStatus, NotificationType, Priority, SLATarget
from app.domain.factories import UserFactory
from app.domain.feedback import Feedback
from app.domain.incident import Comment, Incident
from app.domain.notification import Notification
from app.domain.service import ITService
from app.domain.sla import IncidentSLA, SLAPolicy, SLAViolationRecord
from app.domain.users import Administrator, Technician, TechnicianProfile, User
from app.repositories.orm import (
    AuditRecordRow,
    CategoryRow,
    CommentRow,
    FeedbackRow,
    IncidentRow,
    NotificationRow,
    ServiceDependencyRow,
    ServiceRow,
    SLAPolicyRow,
    SLAViolationRow,
    TechnicianProfileRow,
    UserRow,
)


# --- users ---------------------------------------------------------------------------------

def user_to_domain(row: UserRow) -> User:
    profile = None
    if row.technician_profile is not None:
        p = row.technician_profile
        profile = TechnicianProfile(
            skills=frozenset(p.skills or ()), experience_years=p.experience_years, max_workload=p.max_workload,
            is_available=p.is_available, is_team_lead=p.is_team_lead, team=p.team,
        )
    return UserFactory.create(
        row.role, id=row.id, email=row.email, full_name=row.full_name, password_hash=row.password_hash,
        created_at=ensure_utc(row.created_at), phone=row.phone, department=row.department,
        is_active=row.is_active, profile=profile,
        admin_level=AdminLevel(row.admin_level) if row.admin_level else None,
    )


def user_to_row(user: User, row: UserRow) -> UserRow:
    row.email = user.email
    row.full_name = user.full_name
    row.password_hash = user.password_hash
    row.role = user.role.value
    row.phone = user.phone
    row.department = user.department
    row.is_active = user.is_active
    row.created_at = user.created_at
    row.admin_level = user.admin_level.value if isinstance(user, Administrator) else None
    if isinstance(user, Technician):
        p = user.profile
        profile_row = row.technician_profile or TechnicianProfileRow()
        profile_row.skills = sorted(p.skills)
        profile_row.experience_years = p.experience_years
        profile_row.max_workload = p.max_workload
        profile_row.is_available = p.is_available
        profile_row.is_team_lead = p.is_team_lead
        profile_row.team = p.team
        row.technician_profile = profile_row
    return row


# --- services / categories / SLA policies --------------------------------------------------

def service_to_domain(row: ServiceRow) -> ITService:
    return ITService(
        id=row.id, code=row.code, name=row.name, business_criticality=row.business_criticality,
        owner_team=row.owner_team, description=row.description or "", is_active=row.is_active,
        depends_on={d.depends_on_service_id for d in row.dependencies},
    )


def service_to_row(service: ITService, row: ServiceRow) -> ServiceRow:
    row.code = service.code
    row.name = service.name
    row.description = service.description
    row.business_criticality = service.business_criticality
    row.owner_team = service.owner_team
    row.is_active = service.is_active
    current = {d.depends_on_service_id for d in row.dependencies}
    if current != set(service.depends_on):
        row.dependencies = [ServiceDependencyRow(depends_on_service_id=i) for i in sorted(service.depends_on)]
    return row


def category_to_domain(row: CategoryRow) -> Category:
    return Category(id=row.id, code=row.code, name=row.name, keywords=tuple(row.keywords or ()),
                    is_active=row.is_active)


def category_to_row(category: Category, row: CategoryRow) -> CategoryRow:
    row.code = category.code
    row.name = category.name
    row.keywords = list(category.keywords)
    row.is_active = category.is_active
    return row


def policy_to_domain(row: SLAPolicyRow) -> SLAPolicy:
    return SLAPolicy(
        id=row.id, priority=Priority(row.priority), service_id=row.service_id,
        response_minutes=row.response_minutes, resolution_minutes=row.resolution_minutes,
        warning_threshold_pct=row.warning_threshold_pct,
    )


def policy_to_row(policy: SLAPolicy, row: SLAPolicyRow) -> SLAPolicyRow:
    row.priority = policy.priority.value
    row.service_id = policy.service_id
    row.response_minutes = policy.response_minutes
    row.resolution_minutes = policy.resolution_minutes
    row.warning_threshold_pct = policy.warning_threshold_pct
    return row


# --- incidents ---------------------------------------------------------------------------

def _sla_to_domain(row: IncidentRow) -> IncidentSLA | None:
    if row.sla_response_minutes is None:
        return None
    return IncidentSLA(
        policy_id=row.sla_policy_id, response_minutes=row.sla_response_minutes,
        resolution_minutes=row.sla_resolution_minutes, warning_pct=row.sla_warning_pct,
        started_at=ensure_utc(row.created_at), responded_at=ensure_utc(row.acknowledged_at),
        resolved_at=ensure_utc(row.resolved_at), response_warned=row.response_warned,
        resolution_warned=row.resolution_warned, response_breached=row.response_breached,
        resolution_breached=row.resolution_breached, paused_seconds=row.sla_paused_seconds or 0,
        paused_at=ensure_utc(row.sla_paused_at),
    )


def comment_to_domain(row: CommentRow) -> Comment:
    return Comment(id=row.id, author_id=row.author_id, kind=CommentKind(row.kind), body=row.body,
                   is_internal=row.is_internal, created_at=ensure_utc(row.created_at))


def incident_to_domain(row: IncidentRow) -> Incident:
    return Incident(
        id=row.id, title=row.title, description=row.description, reporter_id=row.reporter_id,
        service_id=row.service_id, impact=row.impact, urgency=row.urgency, affected_users=row.affected_users,
        created_at=ensure_utc(row.created_at), status=IncidentStatus(row.status), category_id=row.category_id,
        suggested_category_id=row.suggested_category_id,
        priority=Priority(row.priority) if row.priority else None, priority_score=row.priority_score,
        assigned_technician_id=row.assigned_technician_id, sla=_sla_to_domain(row),
        updated_at=ensure_utc(row.updated_at), verified_at=ensure_utc(row.verified_at),
        closed_at=ensure_utc(row.closed_at), resolution_summary=row.resolution_summary,
        closure_notes=row.closure_notes, escalation_level=row.escalation_level,
        parent_incident_id=row.parent_incident_id, comments=[comment_to_domain(c) for c in row.comments],
    )


def incident_to_row(incident: Incident, row: IncidentRow, now: datetime) -> list[tuple[Comment, CommentRow]]:
    """Copy incident state onto the row. Returns new (comment, row) pairs whose ids
    must be copied back after flush."""
    row.title = incident.title
    row.description = incident.description
    row.reporter_id = incident.reporter_id
    row.service_id = incident.service_id
    row.category_id = incident.category_id
    row.suggested_category_id = incident.suggested_category_id
    row.impact = incident.impact
    row.urgency = incident.urgency
    row.affected_users = incident.affected_users
    row.priority = incident.priority.value if incident.priority else None
    row.priority_score = incident.priority_score
    row.status = incident.status.value
    row.assigned_technician_id = incident.assigned_technician_id
    row.verified_at = incident.verified_at
    row.closed_at = incident.closed_at
    row.resolution_summary = incident.resolution_summary
    row.closure_notes = incident.closure_notes
    row.escalation_level = incident.escalation_level
    row.parent_incident_id = incident.parent_incident_id
    row.created_at = incident.created_at
    row.updated_at = incident.updated_at
    sla = incident.sla
    if sla is not None:
        row.sla_policy_id = sla.policy_id
        row.sla_response_minutes = sla.response_minutes
        row.sla_resolution_minutes = sla.resolution_minutes
        row.sla_warning_pct = sla.warning_pct
        row.response_due_at = sla.response_due_at
        row.resolution_due_at = sla.resolution_due_at
        row.response_warned = sla.was_warned(SLATarget.RESPONSE)
        row.resolution_warned = sla.was_warned(SLATarget.RESOLUTION)
        row.response_breached = sla.is_breached(SLATarget.RESPONSE)
        row.resolution_breached = sla.is_breached(SLATarget.RESOLUTION)
        row.sla_paused_seconds = sla.paused_seconds
        row.sla_paused_at = sla.paused_at
        row.acknowledged_at = sla.responded_at
        row.resolved_at = sla.resolved_at
        row.sla_status = sla.status(now).value
    new_pairs: list[tuple[Comment, CommentRow]] = []
    for comment in incident.comments:
        if comment.id is None:
            comment_row = CommentRow(author_id=comment.author_id, kind=comment.kind.value, body=comment.body,
                                     is_internal=comment.is_internal, created_at=comment.created_at)
            row.comments.append(comment_row)
            new_pairs.append((comment, comment_row))
    return new_pairs


# --- audit / notifications / violations / feedback ----------------------------------------

def audit_to_domain(row: AuditRecordRow) -> AuditRecord:
    return AuditRecord(
        id=row.id, created_at=ensure_utc(row.created_at), action=row.action, description=row.description,
        actor_id=row.actor_id, actor_name=row.actor_name, incident_id=row.incident_id,
        previous_state=row.previous_state, new_state=row.new_state,
    )


def audit_to_row(record: AuditRecord) -> AuditRecordRow:
    return AuditRecordRow(
        incident_id=record.incident_id, actor_id=record.actor_id, actor_name=record.actor_name,
        action=record.action, previous_state=record.previous_state, new_state=record.new_state,
        description=record.description, created_at=record.created_at,
    )


def notification_to_domain(row: NotificationRow) -> Notification:
    return Notification(
        id=row.id, recipient_id=row.recipient_id, channel=ChannelType(row.channel),
        type=NotificationType(row.event_type), title=row.title, body=row.body,
        created_at=ensure_utc(row.created_at), incident_id=row.incident_id, is_read=row.is_read,
        delivered=row.delivered, delivery_error=row.delivery_error,
    )


def notification_to_row(n: Notification, row: NotificationRow) -> NotificationRow:
    row.recipient_id = n.recipient_id
    row.incident_id = n.incident_id
    row.channel = n.channel.value
    row.event_type = n.type.value
    row.title = n.title
    row.body = n.body
    row.is_read = n.is_read
    row.delivered = n.delivered
    row.delivery_error = n.delivery_error
    row.created_at = n.created_at
    return row


def violation_to_domain(row: SLAViolationRow) -> SLAViolationRecord:
    return SLAViolationRecord(
        id=row.id, incident_id=row.incident_id, target=SLATarget(row.target), due_at=ensure_utc(row.due_at),
        detected_at=ensure_utc(row.detected_at), overdue_minutes=row.overdue_minutes,
    )


def feedback_to_domain(row: FeedbackRow) -> Feedback:
    return Feedback(id=row.id, incident_id=row.incident_id, employee_id=row.employee_id, rating=row.rating,
                    comment=row.comment or "", created_at=ensure_utc(row.created_at))
