"""Domain objects -> response models. A per-request Directory caches the small
reference tables so a page of incidents costs a handful of queries."""

from datetime import datetime
from functools import cached_property

from app.api import schemas
from app.domain.audit import AuditRecord
from app.domain.category import Category
from app.domain.enums import IncidentStatus, SLATarget
from app.domain.incident import Comment, Incident
from app.domain.notification import Notification
from app.domain.repositories import UnitOfWork
from app.domain.service import ITService
from app.domain.sla import SLAPolicy
from app.domain.users import User

FEEDBACK_STATUSES = (IncidentStatus.RESOLVED, IncidentStatus.VERIFIED, IncidentStatus.CLOSED)


class Directory:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    @cached_property
    def users(self) -> dict[int, User]:
        return {u.id: u for u in self._uow.users.list()}

    @cached_property
    def services(self) -> dict[int, ITService]:
        return {s.id: s for s in self._uow.services.list()}

    @cached_property
    def categories(self) -> dict[int, Category]:
        return {c.id: c for c in self._uow.categories.list()}

    def user_ref(self, user_id: int | None) -> schemas.Ref | None:
        user = self.users.get(user_id) if user_id is not None else None
        return schemas.Ref(id=user.id, name=user.full_name, code=user.display_code) if user else None

    def service_ref(self, service_id: int | None) -> schemas.Ref | None:
        s = self.services.get(service_id) if service_id is not None else None
        return schemas.Ref(id=s.id, name=s.name, code=s.code) if s else None

    def category_ref(self, category_id: int | None) -> schemas.Ref | None:
        c = self.categories.get(category_id) if category_id is not None else None
        return schemas.Ref(id=c.id, name=c.name, code=c.code) if c else None


def _summary_fields(i: Incident, d: Directory, now: datetime) -> dict:
    sla_status = i.sla_status(now)
    return dict(
        id=i.id,
        number=i.number,
        title=i.title,
        status=i.status.value,
        priority=i.priority.value if i.priority else None,
        priority_score=i.priority_score,
        impact=i.impact,
        urgency=i.urgency,
        affected_users=i.affected_users,
        service=d.service_ref(i.service_id),
        category=d.category_ref(i.category_id),
        reporter=d.user_ref(i.reporter_id),
        technician=d.user_ref(i.assigned_technician_id),
        sla_status=sla_status.value if sla_status else None,
        response_due_at=i.sla.response_due_at if i.sla else None,
        resolution_due_at=i.sla.resolution_due_at if i.sla else None,
        escalation_level=i.escalation_level,
        created_at=i.created_at,
        updated_at=i.updated_at,
    )


def incident_summary(i: Incident, d: Directory, now: datetime) -> schemas.IncidentSummaryOut:
    return schemas.IncidentSummaryOut(**_summary_fields(i, d, now))


def _sla(i: Incident, now: datetime) -> schemas.SLAOut | None:
    sla = i.sla
    if sla is None:
        return None
    target = sla.active_target()
    return schemas.SLAOut(
        response_minutes=sla.response_minutes,
        resolution_minutes=sla.resolution_minutes,
        warning_pct=sla.warning_pct,
        response_due_at=sla.response_due_at,
        resolution_due_at=sla.resolution_due_at,
        responded_at=sla.responded_at,
        resolved_at=sla.resolved_at,
        response_breached=sla.is_breached(SLATarget.RESPONSE),
        resolution_breached=sla.is_breached(SLATarget.RESOLUTION),
        paused=sla.is_paused,
        paused_seconds=sla.paused_seconds,
        active_target=target.value if target else None,
        elapsed_pct=sla.elapsed_pct(target, now) if target else None,
        status=sla.status(now).value,
    )


def _comment(c: Comment, d: Directory) -> schemas.CommentOut:
    return schemas.CommentOut(
        id=c.id,
        author=d.user_ref(c.author_id),
        kind=c.kind.value,
        body=c.body,
        is_internal=c.is_internal,
        created_at=c.created_at,
    )


def incident_detail(
    i: Incident, viewer: User, d: Directory, uow: UnitOfWork, now: datetime
) -> schemas.IncidentDetailOut:
    links = []
    for link in uow.links.list_for(i.id):
        other = uow.incidents.get(link.other(i.id))
        if other is not None and other.can_be_viewed_by(viewer):
            links.append(
                schemas.LinkOut(
                    incident_id=other.id,
                    number=other.number,
                    title=other.title,
                    status=other.status.value,
                    similarity=link.similarity,
                    link_type=link.link_type.value,
                )
            )
    feedback = uow.feedback.get_for_incident(i.id)
    actions = i.available_actions(viewer, now)
    if i.is_reporter(viewer) and feedback is None and i.status in FEEDBACK_STATUSES:
        actions.append("feedback")
    parent = uow.incidents.get(i.parent_incident_id) if i.parent_incident_id else None
    return schemas.IncidentDetailOut(
        **_summary_fields(i, d, now),
        description=i.description,
        suggested_category=d.category_ref(i.suggested_category_id),
        sla=_sla(i, now),
        comments=[_comment(c, d) for c in i.comments_visible_to(viewer)],
        resolution_summary=i.resolution_summary,
        closure_notes=i.closure_notes,
        acknowledged_at=i.acknowledged_at,
        resolved_at=i.resolved_at,
        verified_at=i.verified_at,
        closed_at=i.closed_at,
        parent_incident=(
            schemas.Ref(id=parent.id, name=parent.title, code=parent.number)
            if parent and parent.can_be_viewed_by(viewer)
            else None
        ),
        links=links,
        feedback=(
            schemas.FeedbackOut(rating=feedback.rating, comment=feedback.comment, created_at=feedback.created_at)
            if feedback
            else None
        ),
        available_actions=actions,
    )


def audit_record(r: AuditRecord) -> schemas.AuditRecordOut:
    return schemas.AuditRecordOut(
        id=r.id,
        created_at=r.created_at,
        actor_id=r.actor_id,
        actor_name=r.actor_name,
        action=r.action,
        incident_id=r.incident_id,
        incident_number=Incident.number_for(r.incident_id) if r.incident_id else None,
        previous_state=r.previous_state,
        new_state=r.new_state,
        description=r.description,
    )


def notification(n: Notification) -> schemas.NotificationOut:
    return schemas.NotificationOut(
        id=n.id,
        channel=n.channel.value,
        type=n.type.value,
        title=n.title,
        body=n.body,
        incident_id=n.incident_id,
        incident_number=Incident.number_for(n.incident_id) if n.incident_id else None,
        is_read=n.is_read,
        delivered=n.delivered,
        delivery_error=n.delivery_error,
        recipient_id=n.recipient_id,
        created_at=n.created_at,
    )


def service(s: ITService) -> schemas.ServiceOut:
    return schemas.ServiceOut(
        id=s.id,
        code=s.code,
        name=s.name,
        description=s.description,
        business_criticality=s.business_criticality,
        owner_team=s.owner_team,
        is_active=s.is_active,
        depends_on=sorted(s.depends_on),
    )


def category(c: Category) -> schemas.CategoryOut:
    return schemas.CategoryOut(id=c.id, code=c.code, name=c.name, keywords=list(c.keywords), is_active=c.is_active)


def policy(p: SLAPolicy) -> schemas.PolicyOut:
    return schemas.PolicyOut(
        id=p.id,
        priority=p.priority,
        service_id=p.service_id,
        response_minutes=p.response_minutes,
        resolution_minutes=p.resolution_minutes,
        warning_threshold_pct=p.warning_threshold_pct,
    )
