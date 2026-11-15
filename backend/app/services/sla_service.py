import logging
from dataclasses import dataclass
from datetime import datetime

from app.domain.clock import Clock
from app.domain.enums import Priority
from app.domain.events import EventBus, SLAViolated, SLAWarningRaised
from app.domain.repositories import UnitOfWork
from app.domain.sla import IncidentSLA, SLAPolicy, SLAPolicyResolver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SLACheckSummary:
    checked: int
    warnings: int
    violations: int


class SLAService:
    def __init__(self, uow: UnitOfWork, clock: Clock, bus: EventBus) -> None:
        self._uow = uow
        self._clock = clock
        self._bus = bus

    def policy_for(self, priority: Priority, service_id: int) -> SLAPolicy:
        """Raises MissingSLAConfigurationError when neither a service nor a default policy exists."""
        return SLAPolicyResolver.resolve(priority, service_id, self._uow.sla_policies.list())

    def clock_for(self, priority: Priority, service_id: int, started_at: datetime) -> IncidentSLA:
        return IncidentSLA.from_policy(self.policy_for(priority, service_id), started_at)

    def run_checks(self) -> SLACheckSummary:
        """One pass of the background monitor: detect warnings/breaches on every
        open incident, publish the events, refresh the stored SLA status, commit."""
        now = self._clock.now()
        warnings = violations = 0
        incidents = [i for i in self._uow.incidents.list_unclosed() if i.sla is not None]
        for incident in incidents:
            incident.check_sla(now)
            self._uow.incidents.update(incident)  # also refreshes the denormalised sla_status column
            for event in incident.pull_events():
                warnings += isinstance(event, SLAWarningRaised)
                violations += isinstance(event, SLAViolated)
                self._bus.publish(event)
        self._uow.commit()
        if warnings or violations:
            logger.info("SLA check: %d incidents, %d warnings, %d violations", len(incidents), warnings, violations)
        return SLACheckSummary(len(incidents), warnings, violations)
