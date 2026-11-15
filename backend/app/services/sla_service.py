import logging
from dataclasses import dataclass
from datetime import datetime

from app.domain.clock import Clock
from app.domain.enums import Priority
from app.domain.events import EventBus, IncidentEscalated, SLAViolated, SLAWarningRaised
from app.domain.repositories import UnitOfWork
from app.domain.sla import IncidentSLA, SLAPolicy, SLAPolicyResolver, SLAViolationRecord
from app.services.escalation_service import EscalationService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SLACheckSummary:
    checked: int
    warnings: int
    violations: int
    escalations: int = 0


class SLAService:
    def __init__(self, uow: UnitOfWork, clock: Clock, bus: EventBus, escalation: EscalationService) -> None:
        self._uow = uow
        self._clock = clock
        self._bus = bus
        self._escalation = escalation

    def policy_for(self, priority: Priority, service_id: int) -> SLAPolicy:
        """Raises MissingSLAConfigurationError when neither a service nor a default policy exists."""
        return SLAPolicyResolver.resolve(priority, service_id, self._uow.sla_policies.list())

    def clock_for(self, priority: Priority, service_id: int, started_at: datetime) -> IncidentSLA:
        return IncidentSLA.from_policy(self.policy_for(priority, service_id), started_at)

    def violations(self, limit: int = 200) -> list[SLAViolationRecord]:
        return self._uow.sla_violations.list(limit=limit)

    def run_checks(self) -> SLACheckSummary:
        """One pass of the background monitor: detect warnings/breaches and due
        escalations on every open incident, publish the events, refresh the stored
        SLA status, commit."""
        now = self._clock.now()
        policy = self._escalation.policy()
        warnings = violations = escalations = 0
        incidents = [i for i in self._uow.incidents.list_unclosed() if i.sla is not None]
        for incident in incidents:
            incident.check_sla(now)
            self._escalation.apply(incident, now, policy)
            self._uow.incidents.update(incident)  # also refreshes the denormalised sla_status column
            for event in incident.pull_events():
                warnings += isinstance(event, SLAWarningRaised)
                violations += isinstance(event, SLAViolated)
                escalations += isinstance(event, IncidentEscalated)
                self._bus.publish(event)
        self._uow.commit()
        if warnings or violations or escalations:
            logger.info(
                "SLA check: %d incidents, %d warnings, %d violations, %d escalations",
                len(incidents),
                warnings,
                violations,
                escalations,
            )
        return SLACheckSummary(len(incidents), warnings, violations, escalations)
