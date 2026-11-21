"""Predicted resolution time: the median working time of comparable resolved incidents.

working time = resolved_at - created_at - time paused in PENDING_INFO (waiting on the reporter is not work)
basis        = same category + priority, else same priority (at least MIN_SAMPLES incidents), else no estimate
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

from app.domain.incident import Incident


@dataclass(frozen=True)
class ResolutionEstimate:
    median_minutes: int
    sample_size: int
    basis: str
    expected_by: datetime | None  # None once the incident is resolved
    reason: str


def working_minutes(incident: Incident) -> float | None:
    sla = incident.sla
    if sla is None or sla.resolved_at is None:
        return None
    worked = sla.resolved_at - incident.created_at - timedelta(seconds=sla.paused_seconds)
    return max(worked.total_seconds() / 60, 0.0)


def describe_minutes(minutes: float) -> str:
    if minutes < 60:
        return f"{round(minutes)} min"
    if minutes < 48 * 60:
        return f"{minutes / 60:.1f} h".replace(".0 h", " h")
    return f"{minutes / 1440:.1f} days".replace(".0 days", " days")


class ResolutionTimeEstimator:
    MIN_SAMPLES = 3

    def estimate(
        self, incident: Incident, history: Sequence[Incident], category_name: str | None = None
    ) -> ResolutionEstimate | None:
        if incident.priority is None:
            return None
        same_priority = [h for h in history if h.id != incident.id and h.priority is incident.priority]
        # Most specific comparable group first; fall back to a wider one when it has too few samples.
        groups: list[tuple[str, list[Incident]]] = []
        if incident.category_id is not None:
            same_category = [h for h in same_priority if h.category_id == incident.category_id]
            groups.append((f"{incident.priority.value} {category_name or 'same-category'} incidents", same_category))
        groups.append((f"{incident.priority.value} incidents", same_priority))
        for basis, group in groups:
            minutes = [m for m in map(working_minutes, group) if m is not None]
            if len(minutes) >= self.MIN_SAMPLES:
                return self._build(incident, basis, minutes)
        return None

    def _build(self, incident: Incident, basis: str, minutes: list[float]) -> ResolutionEstimate:
        typical = median(minutes)
        sla = incident.sla
        expected_by = None
        if sla is not None and sla.resolved_at is None:
            expected_by = incident.created_at + timedelta(minutes=typical, seconds=sla.paused_seconds)
        reason = f"median of {len(minutes)} resolved {basis}: {describe_minutes(typical)}"
        return ResolutionEstimate(round(typical), len(minutes), basis, expected_by, reason)
