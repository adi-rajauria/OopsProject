from app.domain.events import DomainEvent, EventObserver, IncidentEscalated, IncidentEvent
from app.domain.repositories import UnitOfWork
from app.realtime.broadcaster import EventBroadcaster


class RealtimeForwarder(EventObserver):
    """Observer: pushes incident events to live dashboards (SSE).

    The push is registered as an after-commit callback, so clients never see a
    change that was later rolled back.
    """

    def __init__(self, uow: UnitOfWork, broadcaster: EventBroadcaster) -> None:
        self._uow = uow
        self._broadcaster = broadcaster

    def interests(self) -> tuple[type[DomainEvent], ...]:
        return (IncidentEvent,)

    def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, IncidentEvent) or event.incident is None:
            return
        ref = event.incident
        message = {
            "type": "incident",
            "action": event.action,
            "incident_id": ref.id,
            "number": ref.number,
            "title": ref.title,
            "status": ref.status.value,
            "priority": ref.priority.value if ref.priority else None,
            "description": event.describe(),
            "at": event.occurred_at.isoformat(),
        }
        audience = {ref.reporter_id, ref.assignee_id}
        if isinstance(event, IncidentEscalated):
            audience.update(event.recipient_ids)
        recipients = frozenset(uid for uid in audience if uid is not None)
        self._uow.after_commit(lambda: self._broadcaster.publish(message, recipients))
