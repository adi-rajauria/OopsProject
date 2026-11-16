"""Feature 3: SLA risk detection - which open incidents are likely to violate their SLA.

risk score = min(elapsed %, 150) of the active target x priority weight
             + 15 if nobody is assigned yet + 10 if not yet acknowledged past half the response window
level: BREACHED (deadline passed) | HIGH (>= 90) | MEDIUM (>= 60) | LOW
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.enums import IncidentStatus, Priority, SLATarget
from app.domain.incident import Incident

PRIORITY_WEIGHT = {Priority.P1: 1.3, Priority.P2: 1.15, Priority.P3: 1.0, Priority.P4: 0.9}
UNASSIGNED_PENALTY = 15
SLOW_ACK_PENALTY = 10
HIGH, MEDIUM = 90, 60
ELAPSED_CAP = 150  # beyond this an incident is simply "very late"; keeps scores comparable


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BREACHED = "BREACHED"

    @property
    def rank(self) -> int:
        return list(RiskLevel).index(self)


@dataclass(frozen=True)
class SLARiskAssessment:
    incident_id: int
    number: str
    title: str
    priority: Priority
    status: IncidentStatus
    assigned_technician_id: int | None
    target: SLATarget
    due_at: datetime
    elapsed_pct: float
    minutes_left: int
    risk_score: float
    level: RiskLevel
    reasons: tuple[str, ...]


class SLARiskAnalyzer:
    def assess(self, incident: Incident, now: datetime) -> SLARiskAssessment | None:
        sla = incident.sla
        if sla is None or not incident.status.is_open or sla.is_paused:
            return None
        target = sla.active_target()
        if target is None:
            return None
        elapsed = sla.elapsed_pct(target, now)
        weight = PRIORITY_WEIGHT[incident.priority]
        score = min(elapsed, ELAPSED_CAP) * weight
        used = f"{elapsed:.0f}% of {target.value.lower()} time used" if elapsed <= 100 else f"{target.value.lower()} target exceeded"
        reasons = [
            used,
            f"{incident.priority.value} weighting x{weight}",
        ]
        if incident.assigned_technician_id is None:
            score += UNASSIGNED_PENALTY
            reasons.append("no technician assigned")
        if target is SLATarget.RESPONSE and elapsed >= 50:
            score += SLOW_ACK_PENALTY
            reasons.append("not acknowledged after half the response window")
        due = sla.due_at(target)
        minutes_left = int((due - now).total_seconds() // 60)
        if sla.is_breached(target) or now > due:
            level = RiskLevel.BREACHED
            reasons.append(f"deadline passed {abs(minutes_left)} min ago")
        else:
            level = RiskLevel.HIGH if score >= HIGH else RiskLevel.MEDIUM if score >= MEDIUM else RiskLevel.LOW
            reasons.append(f"{minutes_left} min left")
        return SLARiskAssessment(
            incident.id,
            incident.number,
            incident.title,
            incident.priority,
            incident.status,
            incident.assigned_technician_id,
            target,
            due,
            elapsed,
            minutes_left,
            round(score, 1),
            level,
            tuple(reasons),
        )

    def rank(
        self, incidents: Iterable[Incident], now: datetime, minimum: RiskLevel = RiskLevel.MEDIUM
    ) -> list[SLARiskAssessment]:
        assessed = [a for a in (self.assess(i, now) for i in incidents) if a and a.level.rank >= minimum.rank]
        return sorted(assessed, key=lambda a: (-a.level.rank, -a.risk_score))
