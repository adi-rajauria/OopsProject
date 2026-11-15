"""Domain events + EventBus (Observer pattern).

The Incident aggregate raises events; services publish them on the EventBus;
observers (audit logger, notification dispatcher, SLA tracker, SSE broadcaster)
react without the Incident knowing they exist.
"""

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import CommentKind, IncidentStatus, Priority, SLATarget, Transition

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncidentRef:
    """Snapshot of the incident fields observers need (avoids re-loading it)."""

    id: int
    number: str
    title: str
    reporter_id: int
    assignee_id: int | None
    priority: Priority | None
    status: IncidentStatus
    service_id: int


@dataclass(frozen=True, kw_only=True)
class DomainEvent(ABC):
    occurred_at: datetime
    actor_id: int | None = None  # None = performed by the system

    @property
    @abstractmethod
    def action(self) -> str: ...

    @abstractmethod
    def describe(self) -> str: ...

    @property
    def previous_state(self) -> str | None:
        return None

    @property
    def new_state(self) -> str | None:
        return None


@dataclass(frozen=True, kw_only=True)
class IncidentEvent(DomainEvent, ABC):
    incident: IncidentRef | None = None  # filled by Incident.pull_events() once the id exists


@dataclass(frozen=True, kw_only=True)
class IncidentCreated(IncidentEvent):
    reporter_code: str
    title: str

    action = "CREATED"

    def describe(self) -> str:
        number = self.incident.number if self.incident else "Incident"
        return f"{number} created by {self.reporter_code}: {self.title}"

    @property
    def new_state(self) -> str:
        return IncidentStatus.NEW.value


@dataclass(frozen=True, kw_only=True)
class IncidentClassified(IncidentEvent):
    category_code: str

    action = "CLASSIFIED"

    def describe(self) -> str:
        return f"Incident classified as {self.category_code}"

    @property
    def previous_state(self) -> str:
        return IncidentStatus.NEW.value

    @property
    def new_state(self) -> str:
        return IncidentStatus.CLASSIFIED.value


@dataclass(frozen=True, kw_only=True)
class PriorityCalculated(IncidentEvent):
    priority: Priority
    score: float
    explanation: str

    action = "PRIORITY_CALCULATED"

    def describe(self) -> str:
        return f"Priority calculated as {self.priority.value} (score {self.score}): {self.explanation}"


@dataclass(frozen=True, kw_only=True)
class PriorityChanged(IncidentEvent):
    old_priority: Priority | None
    new_priority: Priority
    score: float

    action = "PRIORITY_CHANGED"

    def describe(self) -> str:
        old = self.old_priority.value if self.old_priority else "-"
        return f"Priority changed from {old} to {self.new_priority.value} (score {self.score}); SLA deadlines recalculated"


@dataclass(frozen=True, kw_only=True)
class IncidentAssigned(IncidentEvent):
    technician_id: int
    technician_code: str
    technician_name: str
    reason: str
    from_status: IncidentStatus
    previous_technician_id: int | None = None

    action = "ASSIGNED"

    def describe(self) -> str:
        verb = "Reassigned" if self.previous_technician_id else "Assigned"
        return f"{verb} to Technician {self.technician_code} ({self.technician_name}) - {self.reason}"

    @property
    def previous_state(self) -> str:
        return self.from_status.value

    @property
    def new_state(self) -> str:
        return IncidentStatus.ASSIGNED.value


@dataclass(frozen=True, kw_only=True)
class IncidentTransitioned(IncidentEvent):
    """Generic lifecycle move (acknowledge, start work, resolve, verify, close, ...)."""

    transition: Transition
    from_status: IncidentStatus
    to_status: IncidentStatus
    detail: str = ""

    _TEXT = {
        Transition.ACKNOWLEDGE: "Technician acknowledged incident",
        Transition.START_WORK: "Investigation started",
        Transition.REQUEST_INFO: "Technician requested more information (SLA clock paused)",
        Transition.PROVIDE_INFO: "Reporter provided requested information (SLA clock resumed)",
        Transition.RESOLVE: "Incident marked RESOLVED",
        Transition.REOPEN: "Resolution rejected; incident reopened",
        Transition.VERIFY: "Reporter verified the resolution",
        Transition.CLOSE: "Incident CLOSED",
    }

    @property
    def action(self) -> str:
        return self.transition.name

    def describe(self) -> str:
        base = self._TEXT.get(self.transition, self.transition.name)
        return f"{base}: {self.detail}" if self.detail else base

    @property
    def previous_state(self) -> str:
        return self.from_status.value

    @property
    def new_state(self) -> str:
        return self.to_status.value


@dataclass(frozen=True, kw_only=True)
class IncidentUpdated(IncidentEvent):
    changed_fields: tuple[str, ...]

    action = "UPDATED"

    def describe(self) -> str:
        return f"Incident details updated: {', '.join(self.changed_fields)}"


@dataclass(frozen=True, kw_only=True)
class CommentAdded(IncidentEvent):
    kind: CommentKind
    is_internal: bool
    excerpt: str

    action = "COMMENT_ADDED"

    def describe(self) -> str:
        visibility = "internal " if self.is_internal else ""
        return f"{visibility}{self.kind.value.lower().replace('_', ' ')} added: {self.excerpt}"


@dataclass(frozen=True, kw_only=True)
class SLAWarningRaised(IncidentEvent):
    target: SLATarget
    due_at: datetime
    elapsed_pct: float

    action = "SLA_WARNING"

    def describe(self) -> str:
        return f"{self.target.value.lower()} SLA at {self.elapsed_pct}% - due {self.due_at:%Y-%m-%d %H:%M} UTC"


@dataclass(frozen=True, kw_only=True)
class SLAViolated(IncidentEvent):
    target: SLATarget
    due_at: datetime
    overdue_minutes: int

    action = "SLA_VIOLATED"

    def describe(self) -> str:
        return f"{self.target.value.lower()} SLA violated (due {self.due_at:%Y-%m-%d %H:%M} UTC, {self.overdue_minutes} min overdue)"


@dataclass(frozen=True, kw_only=True)
class IncidentEscalated(IncidentEvent):
    level: int
    level_name: str
    recipient_ids: tuple[int, ...]

    action = "ESCALATED"

    def describe(self) -> str:
        return f"Escalated to level {self.level} ({self.level_name}) - not acknowledged in time"


@dataclass(frozen=True, kw_only=True)
class FeedbackSubmitted(IncidentEvent):
    rating: int

    action = "FEEDBACK"

    def describe(self) -> str:
        return f"Reporter feedback submitted: {self.rating}/5"


@dataclass(frozen=True, kw_only=True)
class UserRegistered(DomainEvent):
    user_id: int
    role: str
    email: str

    action = "USER_CREATED"

    def describe(self) -> str:
        return f"{self.role.title()} account {self.email} created"


@dataclass(frozen=True, kw_only=True)
class SettingChanged(DomainEvent):
    key: str
    old_value: str | None
    new_value: str

    action = "SETTING_CHANGED"

    def describe(self) -> str:
        return f"Setting '{self.key}' changed from {self.old_value!r} to {self.new_value!r}"


class EventObserver(ABC):
    """Observer interface: an object that wants to hear about certain event types."""

    @abstractmethod
    def interests(self) -> tuple[type[DomainEvent], ...]: ...

    @abstractmethod
    def handle(self, event: DomainEvent) -> None: ...


Handler = Callable[[DomainEvent], None]


class EventBus:
    """Observer subject. Dispatches by event class, honouring inheritance
    (subscribing to IncidentEvent receives every incident event)."""

    def __init__(self) -> None:
        self._handlers: defaultdict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def attach(self, observer: EventObserver) -> None:
        for event_type in observer.interests():
            self.subscribe(event_type, observer.handle)

    def publish(self, event: DomainEvent) -> None:
        for cls in type(event).__mro__:
            for handler in self._handlers.get(cls, ()):
                handler(event)

    def publish_all(self, events: Iterable[DomainEvent]) -> None:
        for event in events:
            self.publish(event)
