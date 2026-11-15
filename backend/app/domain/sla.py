from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.domain.enums import Priority, SLAStatus, SLATarget
from app.domain.exceptions import InvalidInputError, MissingSLAConfigurationError


class SLAPolicy:
    """Response/resolution targets for one priority, optionally for one service.

    service_id None = organisation-wide default for that priority.
    """

    def __init__(
        self,
        *,
        id: int | None,
        priority: Priority,
        response_minutes: int,
        resolution_minutes: int,
        service_id: int | None = None,
        warning_threshold_pct: int = 75,
    ) -> None:
        self._id = id
        self._priority = Priority(priority)
        self._service_id = service_id
        self._set_targets(response_minutes, resolution_minutes, warning_threshold_pct)

    def _set_targets(self, response_minutes: int, resolution_minutes: int, warning_pct: int) -> None:
        if response_minutes <= 0 or resolution_minutes <= 0:
            raise InvalidInputError("SLA targets must be positive")
        if resolution_minutes < response_minutes:
            raise InvalidInputError("Resolution target cannot be shorter than response target")
        if not 1 <= warning_pct <= 99:
            raise InvalidInputError("Warning threshold must be between 1 and 99 percent")
        self._response_minutes = response_minutes
        self._resolution_minutes = resolution_minutes
        self._warning_threshold_pct = warning_pct

    @property
    def id(self) -> int | None:
        return self._id

    @property
    def priority(self) -> Priority:
        return self._priority

    @property
    def service_id(self) -> int | None:
        return self._service_id

    @property
    def response_minutes(self) -> int:
        return self._response_minutes

    @property
    def resolution_minutes(self) -> int:
        return self._resolution_minutes

    @property
    def warning_threshold_pct(self) -> int:
        return self._warning_threshold_pct

    @property
    def is_default(self) -> bool:
        return self._service_id is None

    def assign_id(self, new_id: int) -> None:
        self._id = new_id

    def update_targets(self, *, response_minutes: int, resolution_minutes: int, warning_threshold_pct: int) -> None:
        self._set_targets(response_minutes, resolution_minutes, warning_threshold_pct)


class SLAPolicyResolver:
    """Finds the applicable policy: service-specific beats the default for that priority."""

    @staticmethod
    def resolve(priority: Priority, service_id: int | None, policies: Iterable[SLAPolicy]) -> SLAPolicy:
        candidates = [p for p in policies if p.priority == priority]
        specific = next((p for p in candidates if service_id is not None and p.service_id == service_id), None)
        if specific is not None:
            return specific
        default = next((p for p in candidates if p.is_default), None)
        if default is None:
            raise MissingSLAConfigurationError(priority.value, service_id)
        return default


class FindingKind(StrEnum):
    WARNING = "WARNING"
    BREACH = "BREACH"


@dataclass(frozen=True)
class SLAFinding:
    """Something the SLA clock noticed: a pre-breach warning or a breach."""

    kind: FindingKind
    target: SLATarget
    due_at: datetime
    detected_at: datetime
    elapsed_pct: float

    @property
    def overdue_minutes(self) -> int:
        return max(0, int((self.detected_at - self.due_at).total_seconds() // 60))


class IncidentSLA:
    """The SLA clock of one incident. Composition: created with the incident and
    has no life of its own. Policy targets are copied in (snapshot) so later
    policy edits do not silently move existing deadlines.

    Rule: a target is breached when the clock passes its deadline strictly
    (now > due). A warning is raised once when elapsed >= warning threshold.

    Pausing: while the incident waits for the reporter (PENDING_INFO) the clock is
    paused - no warnings or breaches are raised, and on resume the resolution
    deadline moves later by the paused time. The response target is never affected
    because PENDING_INFO is only reachable after acknowledgement.
    """

    def __init__(
        self,
        *,
        policy_id: int | None,
        response_minutes: int,
        resolution_minutes: int,
        warning_pct: int,
        started_at: datetime,
        responded_at: datetime | None = None,
        resolved_at: datetime | None = None,
        response_warned: bool = False,
        resolution_warned: bool = False,
        response_breached: bool = False,
        resolution_breached: bool = False,
        paused_seconds: int = 0,
        paused_at: datetime | None = None,
    ) -> None:
        self._policy_id = policy_id
        self._response_minutes = response_minutes
        self._resolution_minutes = resolution_minutes
        self._warning_pct = warning_pct
        self._started_at = started_at
        self._responded_at = responded_at
        self._resolved_at = resolved_at
        self._warned = {SLATarget.RESPONSE: response_warned, SLATarget.RESOLUTION: resolution_warned}
        self._breached = {SLATarget.RESPONSE: response_breached, SLATarget.RESOLUTION: resolution_breached}
        self._paused_total = timedelta(seconds=paused_seconds)  # completed pauses
        self._paused_at = paused_at  # start of the current pause, None when running

    @classmethod
    def from_policy(cls, policy: SLAPolicy, started_at: datetime) -> "IncidentSLA":
        return cls(
            policy_id=policy.id,
            response_minutes=policy.response_minutes,
            resolution_minutes=policy.resolution_minutes,
            warning_pct=policy.warning_threshold_pct,
            started_at=started_at,
        )

    def rebased_on(self, policy: SLAPolicy) -> "IncidentSLA":
        """New clock for a changed priority, keeping the original start time and progress."""
        clock = IncidentSLA.from_policy(policy, self._started_at)
        clock._responded_at = self._responded_at
        clock._resolved_at = self._resolved_at
        clock._breached = dict(self._breached)
        clock._paused_total = self._paused_total
        clock._paused_at = self._paused_at
        return clock

    # --- read-only view ----------------------------------------------------------------
    @property
    def policy_id(self) -> int | None:
        return self._policy_id

    @property
    def response_minutes(self) -> int:
        return self._response_minutes

    @property
    def resolution_minutes(self) -> int:
        return self._resolution_minutes

    @property
    def warning_pct(self) -> int:
        return self._warning_pct

    @property
    def started_at(self) -> datetime:
        return self._started_at

    @property
    def responded_at(self) -> datetime | None:
        return self._responded_at

    @property
    def resolved_at(self) -> datetime | None:
        return self._resolved_at

    @property
    def is_paused(self) -> bool:
        return self._paused_at is not None

    @property
    def paused_at(self) -> datetime | None:
        return self._paused_at

    @property
    def paused_seconds(self) -> int:
        """Total of completed pauses (the current pause is added on resume)."""
        return int(self._paused_total.total_seconds())

    def _paused_until(self, moment: datetime) -> timedelta:
        current = moment - self._paused_at if self._paused_at is not None else timedelta()
        return self._paused_total + current

    @property
    def response_due_at(self) -> datetime:
        return self._started_at + timedelta(minutes=self._response_minutes)

    @property
    def resolution_due_at(self) -> datetime:
        return self._started_at + timedelta(minutes=self._resolution_minutes) + self._paused_total

    def was_warned(self, target: SLATarget) -> bool:
        return self._warned[target]

    def is_breached(self, target: SLATarget) -> bool:
        return self._breached[target]

    def due_at(self, target: SLATarget) -> datetime:
        return self.response_due_at if target is SLATarget.RESPONSE else self.resolution_due_at

    def _met_at(self, target: SLATarget) -> datetime | None:
        return self._responded_at if target is SLATarget.RESPONSE else self._resolved_at

    def elapsed_pct(self, target: SLATarget, now: datetime) -> float:
        end = self._met_at(target) or now
        elapsed = end - self._started_at
        minutes = self._response_minutes
        if target is SLATarget.RESOLUTION:
            elapsed -= self._paused_until(end)
            minutes = self._resolution_minutes
        return round(100 * elapsed.total_seconds() / (minutes * 60), 1)

    def active_target(self) -> SLATarget | None:
        if self._responded_at is None:
            return SLATarget.RESPONSE
        if self._resolved_at is None:
            return SLATarget.RESOLUTION
        return None

    def status(self, now: datetime) -> SLAStatus:
        if any(self._breached.values()):
            return SLAStatus.BREACHED
        pending = [t for t in SLATarget if self._met_at(t) is None]
        if not pending:
            return SLAStatus.MET
        if self.is_paused:
            return SLAStatus.PAUSED
        if any(now > self.due_at(t) for t in pending):
            return SLAStatus.BREACHED
        if any(self.elapsed_pct(t, now) >= self._warning_pct for t in pending):
            return SLAStatus.AT_RISK
        return SLAStatus.ON_TRACK

    # --- behaviour ---------------------------------------------------------------------
    def evaluate(self, now: datetime) -> list[SLAFinding]:
        """Return *new* warnings/breaches since the last evaluation (each reported once).
        A paused clock never produces findings."""
        findings: list[SLAFinding] = []
        if self.is_paused:
            return findings
        for target in SLATarget:
            if self._met_at(target) is not None or self._breached[target]:
                continue
            pct = self.elapsed_pct(target, now)
            if now > self.due_at(target):
                self._breached[target] = True
                findings.append(SLAFinding(FindingKind.BREACH, target, self.due_at(target), now, pct))
            elif pct >= self._warning_pct and not self._warned[target]:
                self._warned[target] = True
                findings.append(SLAFinding(FindingKind.WARNING, target, self.due_at(target), now, pct))
        return findings

    def mark_responded(self, now: datetime) -> list[SLAFinding]:
        findings = self.evaluate(now)
        self._responded_at = now
        return findings

    def mark_resolved(self, now: datetime) -> list[SLAFinding]:
        findings = self.evaluate(now)
        self._resolved_at = now
        return findings

    def pause(self, now: datetime) -> list[SLAFinding]:
        """Stop the clock; anything already overdue is reported first."""
        findings = self.evaluate(now)
        if not self.is_paused:
            self._paused_at = now
        return findings

    def resume(self, now: datetime) -> None:
        if self._paused_at is not None:
            self._paused_total += now - self._paused_at
            self._paused_at = None

    def reopen(self) -> None:
        self._resolved_at = None


@dataclass(frozen=True)
class SLAViolationRecord:
    """Persistent record of a breached SLA target (one per incident per target)."""

    incident_id: int
    target: SLATarget
    due_at: datetime
    detected_at: datetime
    overdue_minutes: int
    id: int | None = None
