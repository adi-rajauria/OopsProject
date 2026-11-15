from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from app.domain.category import Category
from app.domain.enums import CommentKind, IncidentStatus, Permission, Priority, SLAStatus, Transition
from app.domain.events import (
    CommentAdded,
    IncidentAssigned,
    IncidentClassified,
    IncidentCreated,
    IncidentEscalated,
    IncidentEvent,
    IncidentRef,
    IncidentTransitioned,
    IncidentUpdated,
    PriorityCalculated,
    PriorityChanged,
    SLAViolated,
    SLAWarningRaised,
)
from app.domain.exceptions import (
    InvalidIncidentError,
    InvalidInputError,
    InvalidStateTransitionError,
    UnauthorizedOperationError,
)
from app.domain.lifecycle import IncidentState, state_for
from app.domain.sla import FindingKind, IncidentSLA, SLAFinding
from app.domain.strategies.priority import PriorityResult
from app.domain.users import Technician, User
from app.domain.validation import require_range

TITLE_LIMITS = (5, 200)
DESCRIPTION_LIMITS = (10, 5000)
MAX_AFFECTED_USERS = 100_000
UNVERIFIED_CLOSE_AFTER = timedelta(hours=72)


@dataclass
class Comment:
    """Investigation note / info request / reply. Owned by its Incident (composition)."""

    author_id: int
    kind: CommentKind
    body: str
    is_internal: bool
    created_at: datetime
    id: int | None = None


class Incident:
    """Aggregate root for an IT incident.

    Composition: an Incident owns its SLA clock (IncidentSLA), its lifecycle state
    (IncidentState) and its comments - none of them exist without it.
    Association: it refers to its reporter, technician, service and category by id.
    Every state change goes through the State object, so illegal transitions are
    impossible, and every change raises a domain event for the observers.
    """

    def __init__(
        self,
        *,
        id: int | None,
        title: str,
        description: str,
        reporter_id: int,
        service_id: int,
        impact: int,
        urgency: int,
        created_at: datetime,
        affected_users: int = 1,
        status: IncidentStatus = IncidentStatus.NEW,
        category_id: int | None = None,
        suggested_category_id: int | None = None,
        priority: Priority | None = None,
        priority_score: float | None = None,
        assigned_technician_id: int | None = None,
        sla: IncidentSLA | None = None,
        updated_at: datetime | None = None,
        verified_at: datetime | None = None,
        closed_at: datetime | None = None,
        resolution_summary: str | None = None,
        closure_notes: str | None = None,
        escalation_level: int = 0,
        parent_incident_id: int | None = None,
        comments: list[Comment] | None = None,
    ) -> None:
        self._id = id
        self._title = self._valid_text(title, "title", TITLE_LIMITS)
        self._description = self._valid_text(description, "description", DESCRIPTION_LIMITS)
        self._reporter_id = reporter_id
        self._service_id = service_id
        self._impact = require_range(impact, "impact", 1, 4)
        self._urgency = require_range(urgency, "urgency", 1, 4)
        self._affected_users = require_range(affected_users, "affected_users", 1, MAX_AFFECTED_USERS)
        self._state: IncidentState = state_for(status)
        self._category_id = category_id
        self._suggested_category_id = suggested_category_id
        self._priority = Priority(priority) if priority else None
        self._priority_score = priority_score
        self._assigned_technician_id = assigned_technician_id
        self._sla = sla
        self._created_at = created_at
        self._updated_at = updated_at or created_at
        self._verified_at = verified_at
        self._closed_at = closed_at
        self._resolution_summary = resolution_summary
        self._closure_notes = closure_notes
        self._escalation_level = escalation_level
        self._parent_incident_id = parent_incident_id
        self._comments: list[Comment] = list(comments or [])
        self._pending_events: list[IncidentEvent] = []

    @classmethod
    def report(cls, *, reporter: User, title: str, description: str, service_id: int, impact: int,
               urgency: int, affected_users: int, suggested_category_id: int | None, now: datetime) -> "Incident":
        """Named constructor for a brand-new incident (used by IncidentFactory)."""
        incident = cls(
            id=None, title=title, description=description, reporter_id=reporter.id, service_id=service_id,
            impact=impact, urgency=urgency, affected_users=affected_users, created_at=now,
            suggested_category_id=suggested_category_id,
        )
        incident._raise(IncidentCreated(occurred_at=now, actor_id=reporter.id,
                                        reporter_code=f"{reporter.role.value.title()} {reporter.display_code}",
                                        title=incident.title))
        return incident

    # ------------------------------------------------------------------ validation
    @staticmethod
    def _valid_text(value: str, field: str, limits: tuple[int, int]) -> str:
        cleaned = (value or "").strip()
        low, high = limits
        if not low <= len(cleaned) <= high:
            raise InvalidIncidentError(
                f"Incident {field} must be between {low} and {high} characters", details={"field": field}
            )
        return cleaned

    # ------------------------------------------------------------------ read-only view
    @property
    def id(self) -> int | None:
        return self._id

    @property
    def number(self) -> str:
        return f"INC{1000 + self._id}" if self._id is not None else "INC-NEW"

    @staticmethod
    def id_from_number(number: str) -> int | None:
        digits = number.strip().upper().removeprefix("INC")
        return int(digits) - 1000 if digits.isdigit() and int(digits) > 1000 else None

    @property
    def title(self) -> str:
        return self._title

    @property
    def description(self) -> str:
        return self._description

    @property
    def reporter_id(self) -> int:
        return self._reporter_id

    @property
    def service_id(self) -> int:
        return self._service_id

    @property
    def category_id(self) -> int | None:
        return self._category_id

    @property
    def suggested_category_id(self) -> int | None:
        return self._suggested_category_id

    @property
    def impact(self) -> int:
        return self._impact

    @property
    def urgency(self) -> int:
        return self._urgency

    @property
    def affected_users(self) -> int:
        return self._affected_users

    @property
    def status(self) -> IncidentStatus:
        return self._state.status

    @property
    def priority(self) -> Priority | None:
        return self._priority

    @property
    def priority_score(self) -> float | None:
        return self._priority_score

    @property
    def assigned_technician_id(self) -> int | None:
        return self._assigned_technician_id

    @property
    def sla(self) -> IncidentSLA | None:
        return self._sla

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    @property
    def acknowledged_at(self) -> datetime | None:
        return self._sla.responded_at if self._sla else None

    @property
    def resolved_at(self) -> datetime | None:
        return self._sla.resolved_at if self._sla else None

    @property
    def verified_at(self) -> datetime | None:
        return self._verified_at

    @property
    def closed_at(self) -> datetime | None:
        return self._closed_at

    @property
    def resolution_summary(self) -> str | None:
        return self._resolution_summary

    @property
    def closure_notes(self) -> str | None:
        return self._closure_notes

    @property
    def escalation_level(self) -> int:
        return self._escalation_level

    @property
    def parent_incident_id(self) -> int | None:
        return self._parent_incident_id

    @property
    def comments(self) -> tuple[Comment, ...]:
        return tuple(self._comments)

    def allowed_transitions(self) -> tuple[Transition, ...]:
        return self._state.allowed_transitions()

    def sla_status(self, now: datetime) -> SLAStatus | None:
        return self._sla.status(now) if self._sla else None

    def is_reporter(self, user: User) -> bool:
        return user.id == self._reporter_id

    def is_assignee(self, user: User) -> bool:
        return self._assigned_technician_id is not None and user.id == self._assigned_technician_id

    def can_be_viewed_by(self, user: User) -> bool:
        return user.has_permission(Permission.VIEW_ALL_INCIDENTS) or self.is_reporter(user)

    def comments_visible_to(self, user: User) -> tuple[Comment, ...]:
        if user.has_permission(Permission.VIEW_ALL_INCIDENTS):
            return self.comments
        return tuple(c for c in self._comments if not c.is_internal)

    def ref(self) -> IncidentRef:
        if self._id is None:
            raise InvalidIncidentError("Incident has not been persisted yet")
        return IncidentRef(
            id=self._id, number=self.number, title=self._title, reporter_id=self._reporter_id,
            assignee_id=self._assigned_technician_id, priority=self._priority,
            status=self.status, service_id=self._service_id,
        )

    # ------------------------------------------------------------------ identity / events
    def assign_id(self, new_id: int) -> None:
        if self._id is not None and self._id != new_id:
            raise InvalidIncidentError("Incident id is immutable once assigned")
        self._id = new_id

    def pull_events(self) -> list[IncidentEvent]:
        """Hand pending events to the caller (once), stamped with the incident snapshot."""
        ref = self.ref()
        events = [replace(e, incident=ref) for e in self._pending_events]
        self._pending_events.clear()
        return events

    def _raise(self, event: IncidentEvent) -> None:
        self._pending_events.append(event)

    def _move(self, transition: Transition, now: datetime) -> IncidentStatus:
        """Delegate to the current State; returns the previous status."""
        previous = self.status
        self._state = self._state.apply(transition)
        self._updated_at = now
        return previous

    def _moved(self, transition: Transition, actor: User | None, now: datetime, detail: str = "") -> None:
        previous = self._move(transition, now)
        self._raise(IncidentTransitioned(
            occurred_at=now, actor_id=actor.id if actor else None, transition=transition,
            from_status=previous, to_status=self.status, detail=detail,
        ))

    def _record_sla_findings(self, findings: list[SLAFinding]) -> None:
        for f in findings:
            if f.kind is FindingKind.WARNING:
                self._raise(SLAWarningRaised(occurred_at=f.detected_at, target=f.target, due_at=f.due_at,
                                             elapsed_pct=f.elapsed_pct))
            else:
                self._raise(SLAViolated(occurred_at=f.detected_at, target=f.target, due_at=f.due_at,
                                        overdue_minutes=f.overdue_minutes))

    # ------------------------------------------------------------------ guards
    def _require_assignee(self, actor: User, action: str) -> None:
        if not (isinstance(actor, Technician) and self.is_assignee(actor)):
            raise UnauthorizedOperationError(f"Only the assigned technician can {action} {self.number}")

    def _require_reporter(self, actor: User, action: str) -> None:
        if not self.is_reporter(actor):
            raise UnauthorizedOperationError(f"Only the reporter can {action} {self.number}")

    @staticmethod
    def _require_text(value: str, field: str, min_len: int = 3) -> str:
        cleaned = (value or "").strip()
        if len(cleaned) < min_len or len(cleaned) > 5000:
            raise InvalidInputError(f"{field} must be between {min_len} and 5000 characters", details={"field": field})
        return cleaned

    def _add_comment(self, actor: User, kind: CommentKind, body: str, internal: bool, now: datetime) -> None:
        self._comments.append(Comment(author_id=actor.id, kind=kind, body=body, is_internal=internal, created_at=now))

    # ------------------------------------------------------------------ lifecycle behaviour
    def classify(self, *, category: Category, priority: PriorityResult, sla: IncidentSLA, now: datetime) -> None:
        """NEW -> CLASSIFIED: category, priority and SLA are fixed together (system action)."""
        self._move(Transition.CLASSIFY, now)
        self._category_id = category.id
        self._priority = priority.priority
        self._priority_score = priority.score
        self._sla = sla
        self._raise(IncidentClassified(occurred_at=now, category_code=category.code))
        self._raise(PriorityCalculated(occurred_at=now, priority=priority.priority, score=priority.score,
                                       explanation=priority.explanation))

    def assign(self, technician: Technician, *, actor: User | None, reason: str, now: datetime) -> None:
        if actor is not None and not actor.has_permission(Permission.ASSIGN_INCIDENTS):
            raise UnauthorizedOperationError("Only administrators can assign incidents")
        if technician.id == self._assigned_technician_id:
            raise InvalidInputError(f"{self.number} is already assigned to {technician.full_name}")
        previous_technician = self._assigned_technician_id
        previous_status = self._move(Transition.ASSIGN, now)
        self._assigned_technician_id = technician.id
        self._raise(IncidentAssigned(
            occurred_at=now, actor_id=actor.id if actor else None, technician_id=technician.id,
            technician_code=technician.display_code, technician_name=technician.full_name, reason=reason,
            from_status=previous_status, previous_technician_id=previous_technician,
        ))

    def acknowledge(self, actor: User, now: datetime) -> None:
        self._require_assignee(actor, "acknowledge")
        self._moved(Transition.ACKNOWLEDGE, actor, now)
        self._record_sla_findings(self._sla.mark_responded(now))

    def start_work(self, actor: User, now: datetime) -> None:
        self._require_assignee(actor, "start work on")
        self._moved(Transition.START_WORK, actor, now)

    def request_info(self, actor: User, question: str, now: datetime) -> None:
        self._require_assignee(actor, "request information on")
        question = self._require_text(question, "question")
        self._moved(Transition.REQUEST_INFO, actor, now, detail=question[:120])
        self._add_comment(actor, CommentKind.INFO_REQUEST, question, False, now)
        self._record_sla_findings(self._sla.pause(now))

    def provide_info(self, actor: User, answer: str, now: datetime) -> None:
        self._require_reporter(actor, "answer information requests on")
        answer = self._require_text(answer, "answer")
        self._moved(Transition.PROVIDE_INFO, actor, now, detail=answer[:120])
        self._add_comment(actor, CommentKind.INFO_REPLY, answer, False, now)
        self._sla.resume(now)

    def resolve(self, actor: User, summary: str, now: datetime) -> None:
        self._require_assignee(actor, "resolve")
        summary = self._require_text(summary, "resolution summary", min_len=10)
        self._moved(Transition.RESOLVE, actor, now, detail=summary[:120])
        self._resolution_summary = summary
        self._add_comment(actor, CommentKind.RESOLUTION, summary, False, now)
        self._record_sla_findings(self._sla.mark_resolved(now))

    def reopen(self, actor: User, reason: str, now: datetime) -> None:
        self._require_reporter(actor, "reopen")
        reason = self._require_text(reason, "reason")
        self._moved(Transition.REOPEN, actor, now, detail=reason[:120])
        self._sla.reopen()
        self._add_comment(actor, CommentKind.COMMENT, f"Resolution rejected: {reason}", False, now)

    def verify(self, actor: User, now: datetime) -> None:
        self._require_reporter(actor, "verify")
        self._moved(Transition.VERIFY, actor, now)
        self._verified_at = now

    def close(self, actor: User, notes: str | None, now: datetime) -> None:
        if self.status is IncidentStatus.RESOLVED:
            self._check_override_close(actor, now)
        elif not (self.is_assignee(actor) or actor.has_permission(Permission.OVERRIDE_CLOSE)):
            raise UnauthorizedOperationError("Only the assigned technician or an administrator can close incidents")
        detail = (notes or "").strip()
        if self.status is IncidentStatus.RESOLVED:
            detail = f"closed without verification (admin override) {detail}".strip()
        self._moved(Transition.CLOSE, actor, now, detail=detail[:200])
        self._closure_notes = detail or None
        self._closed_at = now

    def _check_override_close(self, actor: User, now: datetime) -> None:
        """Business rule: an unverified RESOLVED incident may only be closed by an
        administrator once the reporter has had 72 h to verify it."""
        if not actor.has_permission(Permission.OVERRIDE_CLOSE):
            raise InvalidStateTransitionError(self.status.value, "close (awaiting reporter verification)")
        if self.resolved_at is None or now - self.resolved_at < UNVERIFIED_CLOSE_AFTER:
            raise InvalidStateTransitionError(self.status.value, "close (verification window of 72h still open)")

    # ------------------------------------------------------------------ non-transition behaviour
    def add_comment(self, actor: User, body: str, *, internal: bool, now: datetime) -> Comment:
        if not self._state.accepts_comments:
            raise InvalidIncidentError(f"{self.number} is closed; comments are not accepted")
        if not self.can_be_viewed_by(actor):
            raise UnauthorizedOperationError(f"You cannot comment on {self.number}")
        staff = actor.has_permission(Permission.VIEW_ALL_INCIDENTS)
        if internal and not staff:
            raise UnauthorizedOperationError("Only support staff can add internal notes")
        body = self._require_text(body, "comment", min_len=2)
        kind = CommentKind.NOTE if staff else CommentKind.COMMENT
        self._add_comment(actor, kind, body, internal, now)
        self._updated_at = now
        self._raise(CommentAdded(occurred_at=now, actor_id=actor.id, kind=kind, is_internal=internal,
                                 excerpt=body[:80]))
        return self._comments[-1]

    def update_details(
        self,
        actor: User,
        now: datetime,
        *,
        title: str | None = None,
        description: str | None = None,
        impact: int | None = None,
        urgency: int | None = None,
        affected_users: int | None = None,
        category: Category | None = None,
    ) -> tuple[str, ...]:
        """Edit descriptive fields. Returns the changed field names so the caller
        knows whether priority must be recalculated."""
        if not self._state.accepts_updates:
            raise InvalidStateTransitionError(self.status.value, "update")
        if not (self.is_reporter(actor) or self.is_assignee(actor)
                or actor.has_permission(Permission.ASSIGN_INCIDENTS)):
            raise UnauthorizedOperationError(f"You cannot update {self.number}")
        if category is not None and not actor.has_permission(Permission.VIEW_ALL_INCIDENTS):
            raise UnauthorizedOperationError("Only support staff can re-categorise incidents")
        candidate = {
            "title": self._valid_text(title, "title", TITLE_LIMITS) if title is not None else None,
            "description": (self._valid_text(description, "description", DESCRIPTION_LIMITS)
                            if description is not None else None),
            "impact": require_range(impact, "impact", 1, 4) if impact is not None else None,
            "urgency": require_range(urgency, "urgency", 1, 4) if urgency is not None else None,
            "affected_users": (require_range(affected_users, "affected_users", 1, MAX_AFFECTED_USERS)
                               if affected_users is not None else None),
            "category_id": category.id if category is not None else None,
        }
        changed = tuple(k for k, v in candidate.items() if v is not None and v != getattr(self, f"_{k}"))
        for name in changed:
            setattr(self, f"_{name}", candidate[name])
        if changed:
            self._updated_at = now
            self._raise(IncidentUpdated(occurred_at=now, actor_id=actor.id, changed_fields=changed))
        return changed

    def reprioritize(self, result: PriorityResult, sla: IncidentSLA, *, actor: User | None, now: datetime) -> bool:
        """Apply a recalculated priority; deadlines are rebased on the original start time."""
        if result.priority == self._priority and result.score == self._priority_score:
            return False
        old = self._priority
        self._priority = result.priority
        self._priority_score = result.score
        self._sla = sla
        self._updated_at = now
        if old != result.priority:
            self._raise(PriorityChanged(occurred_at=now, actor_id=actor.id if actor else None,
                                        old_priority=old, new_priority=result.priority, score=result.score))
        return True

    def check_sla(self, now: datetime) -> bool:
        """Called by the background monitor. Returns True if something new was detected."""
        if self._sla is None or self.status is IncidentStatus.CLOSED:
            return False
        findings = self._sla.evaluate(now)
        self._record_sla_findings(findings)
        return bool(findings)

    def escalate(self, *, level: int, level_name: str, recipient_ids: tuple[int, ...], now: datetime) -> None:
        if level <= self._escalation_level:
            raise InvalidInputError("Escalation level can only increase")
        self._escalation_level = level
        self._updated_at = now
        self._raise(IncidentEscalated(occurred_at=now, level=level, level_name=level_name,
                                      recipient_ids=recipient_ids))

    def link_to_parent(self, parent_id: int) -> None:
        if parent_id == self._id:
            raise InvalidInputError("An incident cannot be its own parent")
        self._parent_incident_id = parent_id
