"""Incident correlation over the service dependency graph (innovation: dependency view).

* hotspot: a service with >= 3 open incidents reported in the last 2 hours
* upstream cause: a service with recent incidents that depends on another service
  which *also* has recent incidents -> the upstream service is the likely common cause
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from app.domain.incident import Incident
from app.domain.service import ITService

HOTSPOT_THRESHOLD = 3
WINDOW = timedelta(hours=2)


class Health(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    HOTSPOT = "HOTSPOT"


@dataclass(frozen=True)
class ServiceNode:
    service_id: int
    code: str
    name: str
    criticality: int
    open_incidents: int
    recent_incidents: int
    health: Health
    depends_on: tuple[int, ...]


@dataclass(frozen=True)
class CorrelationFinding:
    kind: str  # HOTSPOT | UPSTREAM_CAUSE
    root_service_id: int
    root_service: str
    incident_ids: tuple[int, ...]
    explanation: str


@dataclass(frozen=True)
class CorrelationReport:
    nodes: list[ServiceNode]
    edges: list[tuple[int, int]]  # (service, depends_on)
    findings: list[CorrelationFinding] = field(default_factory=list)

    def finding_for(self, incident_id: int) -> CorrelationFinding | None:
        return next((f for f in self.findings if incident_id in f.incident_ids), None)


class IncidentCorrelator:
    def analyse(self, services: Sequence[ITService], incidents: Sequence[Incident], now: datetime) -> CorrelationReport:
        open_by_service: dict[int, list[Incident]] = defaultdict(list)
        recent_by_service: dict[int, list[Incident]] = defaultdict(list)
        for incident in incidents:
            if incident.status.is_open:
                open_by_service[incident.service_id].append(incident)
                if now - incident.created_at <= WINDOW:
                    recent_by_service[incident.service_id].append(incident)

        by_id = {s.id: s for s in services}
        nodes = [self._node(s, open_by_service[s.id], recent_by_service[s.id]) for s in services]
        edges = [(s.id, dep) for s in services for dep in sorted(s.depends_on) if dep in by_id]
        findings = self._hotspots(by_id, recent_by_service) + self._upstream_causes(services, by_id, recent_by_service)
        return CorrelationReport(nodes, edges, findings)

    @staticmethod
    def _node(service: ITService, open_incidents: list[Incident], recent: list[Incident]) -> ServiceNode:
        health = (
            Health.HOTSPOT
            if len(recent) >= HOTSPOT_THRESHOLD
            else Health.DEGRADED
            if open_incidents
            else Health.HEALTHY
        )
        return ServiceNode(
            service.id,
            service.code,
            service.name,
            service.business_criticality,
            len(open_incidents),
            len(recent),
            health,
            tuple(sorted(service.depends_on)),
        )

    @staticmethod
    def _hotspots(by_id, recent_by_service) -> list[CorrelationFinding]:
        return [
            CorrelationFinding(
                "HOTSPOT",
                sid,
                by_id[sid].name,
                tuple(i.id for i in incidents),
                f"{len(incidents)} incidents on {by_id[sid].name} in the last 2 h - likely one underlying problem",
            )
            for sid, incidents in recent_by_service.items()
            if sid in by_id and len(incidents) >= HOTSPOT_THRESHOLD
        ]

    @staticmethod
    def _upstream_causes(services, by_id, recent_by_service) -> list[CorrelationFinding]:
        findings = []
        for upstream_id, upstream_incidents in recent_by_service.items():
            dependents = [s for s in services if upstream_id in s.depends_on and recent_by_service.get(s.id)]
            if upstream_id not in by_id or not dependents:
                continue
            affected = [i.id for s in dependents for i in recent_by_service[s.id]]
            names = ", ".join(s.name for s in dependents)
            findings.append(
                CorrelationFinding(
                    "UPSTREAM_CAUSE",
                    upstream_id,
                    by_id[upstream_id].name,
                    tuple(affected + [i.id for i in upstream_incidents]),
                    f"{names} depend(s) on {by_id[upstream_id].name}, which also has {len(upstream_incidents)} "
                    f"recent incident(s) - {by_id[upstream_id].name} is the likely common cause",
                )
            )
        return findings
