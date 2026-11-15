"""Which channels a notification goes out on - Strategy pattern.

The dispatcher asks a ChannelSelectionPolicy; swapping the policy (e.g. a
'quiet hours' policy) changes behaviour without touching the dispatcher.
"""

from abc import ABC, abstractmethod

from app.domain.enums import ChannelType, NotificationType, Priority


class ChannelSelectionPolicy(ABC):
    @abstractmethod
    def channels_for(self, notification_type: NotificationType, priority: Priority | None) -> list[ChannelType]: ...


class DefaultChannelSelectionPolicy(ChannelSelectionPolicy):
    """In-app always; e-mail for events a person must act on; SMS only when it is urgent."""

    EMAIL_TYPES = frozenset({
        NotificationType.INCIDENT_ASSIGNED,
        NotificationType.TECHNICIAN_ASSIGNED,
        NotificationType.INFO_REQUESTED,
        NotificationType.INCIDENT_RESOLVED,
        NotificationType.INCIDENT_CLOSED,
        NotificationType.SLA_VIOLATED,
        NotificationType.ESCALATED,
    })
    SMS_TYPES = frozenset({NotificationType.SLA_VIOLATED, NotificationType.ESCALATED})

    def channels_for(self, notification_type: NotificationType, priority: Priority | None) -> list[ChannelType]:
        channels = [ChannelType.IN_APP]
        if notification_type in self.EMAIL_TYPES:
            channels.append(ChannelType.EMAIL)
        urgent_assignment = priority is Priority.P1 and notification_type is NotificationType.INCIDENT_ASSIGNED
        if notification_type in self.SMS_TYPES or urgent_assignment:
            channels.append(ChannelType.SMS)
        return channels
