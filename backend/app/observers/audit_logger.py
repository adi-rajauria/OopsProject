from app.domain.audit import AuditRecord
from app.domain.events import DomainEvent, EventObserver, IncidentEvent
from app.domain.repositories import UnitOfWork


class AuditLogger(EventObserver):
    """Observer: turns every domain event into an immutable audit record.

    It is the single writer of the audit trail, so no business code can forget
    to audit - raising the event is enough.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def interests(self) -> tuple[type[DomainEvent], ...]:
        return (DomainEvent,)

    def handle(self, event: DomainEvent) -> None:
        incident_id = event.incident.id if isinstance(event, IncidentEvent) and event.incident else None
        self._uow.audit.add(AuditRecord(
            created_at=event.occurred_at,
            action=event.action,
            description=event.describe(),
            actor_id=event.actor_id,
            actor_name=self._actor_name(event.actor_id),
            incident_id=incident_id,
            previous_state=event.previous_state,
            new_state=event.new_state,
        ))

    def _actor_name(self, actor_id: int | None) -> str:
        if actor_id is None:
            return "SYSTEM"
        user = self._uow.users.get(actor_id)
        return f"{user.full_name} ({user.display_code})" if user else f"User {actor_id}"
