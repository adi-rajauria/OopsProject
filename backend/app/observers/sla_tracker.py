from app.domain.events import DomainEvent, EventObserver, SLAViolated
from app.domain.repositories import UnitOfWork
from app.domain.sla import SLAViolationRecord


class SLATracker(EventObserver):
    """Observer: records each SLA violation exactly once (for the violations report)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def interests(self) -> tuple[type[DomainEvent], ...]:
        return (SLAViolated,)

    def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, SLAViolated) or event.incident is None:
            return
        if self._uow.sla_violations.exists(event.incident.id, event.target):
            return
        self._uow.sla_violations.add(SLAViolationRecord(
            incident_id=event.incident.id, target=event.target, due_at=event.due_at,
            detected_at=event.occurred_at, overdue_minutes=event.overdue_minutes,
        ))
