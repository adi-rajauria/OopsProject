import logging

from app.domain.audit import AuditTrail
from app.domain.category import Category
from app.domain.clock import Clock
from app.domain.enums import IncidentStatus, Permission
from app.domain.events import EventBus, FeedbackSubmitted
from app.domain.exceptions import (
    CategoryNotFoundError,
    FeedbackAlreadySubmittedError,
    IncidentNotFoundError,
    InvalidIncidentError,
    InvalidStateTransitionError,
    ServiceNotFoundError,
    TechnicianUnavailableError,
    UnauthorizedOperationError,
)
from app.domain.factories import IncidentFactory, NewIncidentData
from app.domain.feedback import Feedback
from app.domain.incident import Comment, Incident
from app.domain.repositories import UnitOfWork
from app.domain.service import ITService
from app.domain.strategies.priority import PriorityCalculator, PriorityInput, PriorityResult
from app.domain.users import User
from app.services.assignment_service import AssignmentService
from app.services.sla_service import SLAService

logger = logging.getLogger(__name__)

PRIORITY_FIELDS = frozenset({"impact", "urgency", "affected_users"})
FEEDBACK_STATUSES = (IncidentStatus.RESOLVED, IncidentStatus.VERIFIED, IncidentStatus.CLOSED)


class IncidentService:
    """Use-case layer for the incident lifecycle.

    Each method: load -> check visibility -> call the domain -> save -> publish
    events -> commit. Business rules live in the domain objects, not here.
    """

    def __init__(self, uow: UnitOfWork, clock: Clock, bus: EventBus, priority_calculator: PriorityCalculator,
                 assignment: AssignmentService, sla: SLAService) -> None:
        self._uow = uow
        self._clock = clock
        self._bus = bus
        self._priority = priority_calculator
        self._assignment = assignment
        self._sla = sla

    # ------------------------------------------------------------------ helpers
    def _service(self, service_id: int) -> ITService:
        service = self._uow.services.get(service_id)
        if service is None:
            raise ServiceNotFoundError(service_id)
        return service

    def _category(self, category_id: int | None) -> Category:
        if category_id is None:
            raise InvalidIncidentError("A category is required", details={"field": "category_id"})
        category = self._uow.categories.get(category_id)
        if category is None or not category.is_active:
            raise CategoryNotFoundError(category_id)
        return category

    def _calculate_priority(self, incident: Incident, service: ITService) -> PriorityResult:
        return self._priority.calculate(PriorityInput(
            impact=incident.impact, urgency=incident.urgency,
            business_criticality=service.business_criticality, affected_users=incident.affected_users,
        ))

    def _save(self, incident: Incident) -> Incident:
        self._uow.incidents.update(incident)
        self._bus.publish_all(incident.pull_events())
        self._uow.commit()
        return incident

    # ------------------------------------------------------------------ queries
    def get(self, incident_id: int, viewer: User) -> Incident:
        incident = self._uow.incidents.get(incident_id)
        if incident is None:
            raise IncidentNotFoundError(incident_id)
        if not incident.can_be_viewed_by(viewer):
            raise UnauthorizedOperationError(f"You are not allowed to view {incident.number}")
        return incident

    def audit_trail(self, incident_id: int, viewer: User) -> AuditTrail:
        self.get(incident_id, viewer)
        return self._uow.audit.trail_for(incident_id)

    def feedback_for(self, incident_id: int, viewer: User) -> Feedback | None:
        self.get(incident_id, viewer)
        return self._uow.feedback.get_for_incident(incident_id)

    # ------------------------------------------------------------------ commands
    def report(self, reporter: User, data: NewIncidentData) -> Incident:
        """Report -> classify -> prioritise -> SLA -> (try to) assign, in one transaction."""
        now = self._clock.now()
        service = self._service(data.service_id)
        category = self._category(data.category_id)
        incident = IncidentFactory.create(reporter, data, service, suggested_category_id=None, now=now)
        priority = self._calculate_priority(incident, service)
        sla = self._sla.clock_for(priority.priority, service.id, now)
        incident.classify(category=category, priority=priority, sla=sla, now=now)
        self._uow.incidents.add(incident)
        self._try_auto_assign(incident)
        return self._save(incident)

    def _try_auto_assign(self, incident: Incident) -> None:
        try:
            self._assignment.auto_assign(incident)
        except TechnicianUnavailableError as exc:
            logger.warning("%s left unassigned: %s", incident.number, exc.message)

    def assign(self, incident_id: int, technician_id: int, actor: User) -> Incident:
        incident = self.get(incident_id, actor)
        self._assignment.manual_assign(incident, technician_id, actor)
        return self._save(incident)

    def auto_assign(self, incident_id: int, actor: User) -> Incident:
        """Admin button: retry automatic assignment with the current strategy."""
        if not actor.has_permission(Permission.ASSIGN_INCIDENTS):
            raise UnauthorizedOperationError("Only administrators can assign incidents")
        incident = self.get(incident_id, actor)
        if incident.status is not IncidentStatus.CLASSIFIED:
            raise InvalidStateTransitionError(incident.status.value, "auto-assign")
        self._assignment.auto_assign(incident)
        return self._save(incident)

    def acknowledge(self, incident_id: int, actor: User) -> Incident:
        incident = self.get(incident_id, actor)
        incident.acknowledge(actor, self._clock.now())
        return self._save(incident)

    def start_work(self, incident_id: int, actor: User) -> Incident:
        incident = self.get(incident_id, actor)
        incident.start_work(actor, self._clock.now())
        return self._save(incident)

    def request_info(self, incident_id: int, actor: User, question: str) -> Incident:
        incident = self.get(incident_id, actor)
        incident.request_info(actor, question, self._clock.now())
        return self._save(incident)

    def provide_info(self, incident_id: int, actor: User, answer: str) -> Incident:
        incident = self.get(incident_id, actor)
        incident.provide_info(actor, answer, self._clock.now())
        return self._save(incident)

    def add_comment(self, incident_id: int, actor: User, body: str, *, internal: bool = False) -> Comment:
        incident = self.get(incident_id, actor)
        comment = incident.add_comment(actor, body, internal=internal, now=self._clock.now())
        self._save(incident)
        return comment

    def resolve(self, incident_id: int, actor: User, summary: str) -> Incident:
        incident = self.get(incident_id, actor)
        incident.resolve(actor, summary, self._clock.now())
        return self._save(incident)

    def reopen(self, incident_id: int, actor: User, reason: str) -> Incident:
        incident = self.get(incident_id, actor)
        incident.reopen(actor, reason, self._clock.now())
        return self._save(incident)

    def verify(self, incident_id: int, actor: User, *, rating: int | None = None, comment: str = "") -> Incident:
        incident = self.get(incident_id, actor)
        incident.verify(actor, self._clock.now())
        self._save(incident)
        if rating is not None:
            self.submit_feedback(incident_id, actor, rating, comment)
        return incident

    def close(self, incident_id: int, actor: User, notes: str | None = None) -> Incident:
        incident = self.get(incident_id, actor)
        incident.close(actor, notes, self._clock.now())
        return self._save(incident)

    def submit_feedback(self, incident_id: int, actor: User, rating: int, comment: str = "") -> Feedback:
        incident = self.get(incident_id, actor)
        if not incident.is_reporter(actor):
            raise UnauthorizedOperationError("Only the reporter can give feedback")
        if incident.status not in FEEDBACK_STATUSES:
            raise InvalidStateTransitionError(incident.status.value, "give feedback (incident not resolved yet)")
        if self._uow.feedback.get_for_incident(incident_id) is not None:
            raise FeedbackAlreadySubmittedError(f"Feedback for {incident.number} was already submitted")
        now = self._clock.now()
        feedback = self._uow.feedback.add(Feedback(incident_id=incident_id, employee_id=actor.id, rating=rating,
                                                   comment=(comment or "").strip(), created_at=now))
        self._bus.publish(FeedbackSubmitted(occurred_at=now, actor_id=actor.id, incident=incident.ref(),
                                            rating=rating))
        self._uow.commit()
        return feedback

    def update_details(self, incident_id: int, actor: User, *, title: str | None = None,
                       description: str | None = None, impact: int | None = None, urgency: int | None = None,
                       affected_users: int | None = None, category_id: int | None = None) -> Incident:
        """Edit an open incident; impact/urgency/affected-user changes re-run the
        priority strategy and rebase the SLA deadlines on the original creation time."""
        incident = self.get(incident_id, actor)
        now = self._clock.now()
        category = self._category(category_id) if category_id is not None else None
        changed = incident.update_details(actor, now, title=title, description=description, impact=impact,
                                          urgency=urgency, affected_users=affected_users, category=category)
        if PRIORITY_FIELDS.intersection(changed) and incident.sla is not None:
            result = self._calculate_priority(incident, self._service(incident.service_id))
            sla = incident.sla.rebased_on(self._sla.policy_for(result.priority, incident.service_id))
            incident.reprioritize(result, sla, actor=actor, now=now)
        return self._save(incident)
