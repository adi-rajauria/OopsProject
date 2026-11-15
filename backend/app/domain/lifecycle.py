"""Incident lifecycle - State pattern.

Each concrete state overrides only the transitions it allows and returns the next
state. Everything else falls through to the base class, which raises
InvalidStateTransitionError. Adding a state = adding one class + one map entry.

    NEW -> CLASSIFIED -> ASSIGNED -> ACKNOWLEDGED -> IN_PROGRESS -> RESOLVED -> VERIFIED -> CLOSED
                         ASSIGNED -> ASSIGNED (reassign)
                                                   IN_PROGRESS <-> PENDING_INFO
                                                   RESOLVED -> IN_PROGRESS (reopen)
                                                   RESOLVED -> CLOSED (admin override, checked by Incident)
"""

from abc import ABC
from typing import ClassVar

from app.domain.enums import IncidentStatus, Transition
from app.domain.exceptions import InvalidStateTransitionError


class IncidentState(ABC):
    status: ClassVar[IncidentStatus]

    def _illegal(self, transition: Transition) -> "IncidentState":
        raise InvalidStateTransitionError(self.status.value, transition.value)

    def classify(self) -> "IncidentState":
        return self._illegal(Transition.CLASSIFY)

    def assign(self) -> "IncidentState":
        return self._illegal(Transition.ASSIGN)

    def acknowledge(self) -> "IncidentState":
        return self._illegal(Transition.ACKNOWLEDGE)

    def start_work(self) -> "IncidentState":
        return self._illegal(Transition.START_WORK)

    def request_info(self) -> "IncidentState":
        return self._illegal(Transition.REQUEST_INFO)

    def provide_info(self) -> "IncidentState":
        return self._illegal(Transition.PROVIDE_INFO)

    def resolve(self) -> "IncidentState":
        return self._illegal(Transition.RESOLVE)

    def reopen(self) -> "IncidentState":
        return self._illegal(Transition.REOPEN)

    def verify(self) -> "IncidentState":
        return self._illegal(Transition.VERIFY)

    def close(self) -> "IncidentState":
        return self._illegal(Transition.CLOSE)

    def apply(self, transition: Transition) -> "IncidentState":
        """Dispatch by name, e.g. apply(Transition.RESOLVE) -> self.resolve()."""
        return getattr(self, transition.value)()

    @classmethod
    def allowed_transitions(cls) -> tuple[Transition, ...]:
        """A transition is allowed iff this state overrides the base method."""
        return tuple(t for t in Transition if getattr(cls, t.value) is not getattr(IncidentState, t.value))

    @property
    def accepts_updates(self) -> bool:
        """Can descriptive fields (impact, urgency, text) still be edited?"""
        return self.status.is_open

    @property
    def accepts_comments(self) -> bool:
        return self.status is not IncidentStatus.CLOSED


class NewState(IncidentState):
    status = IncidentStatus.NEW

    def classify(self) -> IncidentState:
        return ClassifiedState()


class ClassifiedState(IncidentState):
    status = IncidentStatus.CLASSIFIED

    def assign(self) -> IncidentState:
        return AssignedState()


class AssignedState(IncidentState):
    status = IncidentStatus.ASSIGNED

    def assign(self) -> IncidentState:
        return AssignedState()

    def acknowledge(self) -> IncidentState:
        return AcknowledgedState()


class AcknowledgedState(IncidentState):
    status = IncidentStatus.ACKNOWLEDGED

    def start_work(self) -> IncidentState:
        return InProgressState()


class InProgressState(IncidentState):
    status = IncidentStatus.IN_PROGRESS

    def request_info(self) -> IncidentState:
        return PendingInfoState()

    def resolve(self) -> IncidentState:
        return ResolvedState()


class PendingInfoState(IncidentState):
    status = IncidentStatus.PENDING_INFO

    def provide_info(self) -> IncidentState:
        return InProgressState()


class ResolvedState(IncidentState):
    status = IncidentStatus.RESOLVED

    def verify(self) -> IncidentState:
        return VerifiedState()

    def reopen(self) -> IncidentState:
        return InProgressState()

    def close(self) -> IncidentState:
        return ClosedState()


class VerifiedState(IncidentState):
    status = IncidentStatus.VERIFIED

    def close(self) -> IncidentState:
        return ClosedState()


class ClosedState(IncidentState):
    status = IncidentStatus.CLOSED


_STATES: dict[IncidentStatus, type[IncidentState]] = {
    cls.status: cls
    for cls in (NewState, ClassifiedState, AssignedState, AcknowledgedState, InProgressState,
                PendingInfoState, ResolvedState, VerifiedState, ClosedState)
}


def state_for(status: IncidentStatus) -> IncidentState:
    return _STATES[IncidentStatus(status)]()
