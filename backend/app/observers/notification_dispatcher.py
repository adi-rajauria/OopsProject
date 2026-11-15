import logging
from collections.abc import Iterator

from app.domain.enums import NotificationType, Transition
from app.domain.events import (
    DomainEvent,
    EventObserver,
    IncidentAssigned,
    IncidentCreated,
    IncidentEscalated,
    IncidentEvent,
    IncidentTransitioned,
    PriorityChanged,
    SLAViolated,
    SLAWarningRaised,
)
from app.domain.exceptions import NotificationDeliveryError
from app.domain.factories import NotificationFactory
from app.domain.repositories import UnitOfWork
from app.domain.strategies.channel_selection import ChannelSelectionPolicy
from app.domain.users import User
from app.notifications.channels import ChannelRegistry

logger = logging.getLogger(__name__)

Target = tuple[int | None, NotificationType, str]


class NotificationDispatcher(EventObserver):
    """Observer: decides *who* hears about an event; the ChannelSelectionPolicy
    (Strategy) decides *how*; channels (Adapters) deliver. A failed delivery is
    recorded on the notification and never rolls back the business change."""

    def __init__(self, uow: UnitOfWork, channels: ChannelRegistry, policy: ChannelSelectionPolicy) -> None:
        self._uow = uow
        self._channels = channels
        self._policy = policy

    def interests(self) -> tuple[type[DomainEvent], ...]:
        return (
            IncidentCreated,
            IncidentAssigned,
            PriorityChanged,
            IncidentTransitioned,
            SLAWarningRaised,
            SLAViolated,
            IncidentEscalated,
        )

    def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, IncidentEvent) or event.incident is None:
            return
        seen: set[tuple[int, NotificationType]] = set()
        for recipient_id, ntype, detail in self._targets(event):
            if recipient_id is None or (recipient_id, ntype) in seen:
                continue
            seen.add((recipient_id, ntype))
            is_own_action = recipient_id == event.actor_id and not isinstance(event, IncidentCreated)
            recipient = self._uow.users.get(recipient_id)
            if recipient is None or not recipient.is_active or is_own_action:
                continue
            self._send(recipient, ntype, detail, event)

    def _send(self, recipient: User, ntype: NotificationType, detail: str, event: IncidentEvent) -> None:
        for channel_type in self._policy.channels_for(ntype, event.incident.priority):
            channel = self._channels.get(channel_type)
            if channel is None or not channel.can_reach(recipient):
                continue
            notification = NotificationFactory.create(
                recipient=recipient,
                channel=channel_type,
                type=ntype,
                incident=event.incident,
                detail=detail,
                now=event.occurred_at,
            )
            try:
                channel.deliver(notification, recipient)
                notification.mark_delivered()
            except NotificationDeliveryError as exc:
                notification.mark_failed(exc.message)
                logger.warning("Notification %s to user %s failed: %s", ntype, recipient.id, exc.message)
            self._uow.notifications.add(notification)

    def _admin_ids(self) -> list[int]:
        return [a.id for a in self._uow.users.list_administrators() if a.is_active]

    def _targets(self, event: IncidentEvent) -> Iterator[Target]:
        ref = event.incident
        match event:
            case IncidentCreated():
                yield ref.reporter_id, NotificationType.INCIDENT_CREATED, "You can track progress on its page."
            case IncidentAssigned():
                yield event.technician_id, NotificationType.INCIDENT_ASSIGNED, event.reason
                yield (
                    ref.reporter_id,
                    NotificationType.TECHNICIAN_ASSIGNED,
                    f"{event.technician_name} is now handling '{ref.title}'.",
                )
            case PriorityChanged():
                yield ref.reporter_id, NotificationType.PRIORITY_CHANGED, event.describe()
                yield ref.assignee_id, NotificationType.PRIORITY_CHANGED, event.describe()
            case IncidentTransitioned(transition=Transition.REQUEST_INFO):
                yield ref.reporter_id, NotificationType.INFO_REQUESTED, event.detail
            case IncidentTransitioned(transition=Transition.PROVIDE_INFO):
                yield ref.assignee_id, NotificationType.INFO_PROVIDED, event.detail
            case IncidentTransitioned(transition=Transition.RESOLVE):
                yield ref.reporter_id, NotificationType.INCIDENT_RESOLVED, event.detail
            case IncidentTransitioned(transition=Transition.REOPEN):
                yield ref.assignee_id, NotificationType.INCIDENT_REOPENED, event.describe()
            case IncidentTransitioned(transition=Transition.CLOSE):
                yield ref.reporter_id, NotificationType.INCIDENT_CLOSED, event.describe()
            case IncidentTransitioned(transition=Transition.VERIFY):
                yield ref.assignee_id, NotificationType.STATUS_CHANGED, event.describe()
            case IncidentTransitioned():
                yield ref.reporter_id, NotificationType.STATUS_CHANGED, event.describe()
            case SLAWarningRaised():
                for uid in [ref.assignee_id] if ref.assignee_id else self._admin_ids():
                    yield uid, NotificationType.SLA_WARNING, event.describe()
            case SLAViolated():
                for uid in [ref.assignee_id, *self._admin_ids()]:
                    yield uid, NotificationType.SLA_VIOLATED, event.describe()
            case IncidentEscalated():
                for uid in event.recipient_ids:
                    yield uid, NotificationType.ESCALATED, event.describe()
