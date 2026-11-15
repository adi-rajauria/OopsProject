"""Feature 4: automatic escalation chain for unacknowledged critical incidents.

Technician -> Team Lead -> System Administrator -> IT Manager.
Level 1 fires as soon as the response deadline passes without acknowledgement;
each further level fires one more response window later (P1: due+0, +5, +10, +15 min).
"""

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import IncidentStatus, Priority
from app.domain.incident import Incident

UNACKNOWLEDGED = (IncidentStatus.CLASSIFIED, IncidentStatus.ASSIGNED)


@dataclass(frozen=True)
class EscalationStep:
    level: int
    name: str


CHAIN: tuple[EscalationStep, ...] = (
    EscalationStep(1, "Technician"),
    EscalationStep(2, "Team Lead"),
    EscalationStep(3, "System Administrator"),
    EscalationStep(4, "IT Manager"),
)


class EscalationPolicy:
    def __init__(self, priorities: frozenset[Priority] = frozenset({Priority.P1})) -> None:
        self._priorities = priorities

    @property
    def priorities(self) -> frozenset[Priority]:
        return self._priorities

    def due_level(self, incident: Incident, now: datetime) -> int:
        """Highest chain level that should have been reached by `now` (0 = none)."""
        sla = incident.sla
        if sla is None or incident.priority not in self._priorities or incident.status not in UNACKNOWLEDGED:
            return 0
        overdue = (now - sla.response_due_at).total_seconds()
        if overdue <= 0:
            return 0
        window = sla.response_minutes * 60
        return min(len(CHAIN), 1 + int(overdue // window))

    def pending_steps(self, incident: Incident, now: datetime) -> list[EscalationStep]:
        """Steps not yet taken; walked one by one so every level is audited and notified."""
        target = self.due_level(incident, now)
        return [step for step in CHAIN if incident.escalation_level < step.level <= target]
