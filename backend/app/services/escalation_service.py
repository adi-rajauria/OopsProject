from datetime import datetime

from app.domain.clock import Clock
from app.domain.enums import AdminLevel, Permission, Priority
from app.domain.events import AdministrativeChange, EventBus
from app.domain.exceptions import UnauthorizedOperationError
from app.domain.incident import Incident
from app.domain.repositories import UnitOfWork
from app.domain.users import Technician, User
from app.intelligence.escalation import EscalationPolicy, EscalationStep

INCLUDE_P2_SETTING = "escalation.include_p2"


class EscalationService:
    """Walks unacknowledged critical incidents up the escalation chain and decides
    who is notified at each level. Called by the SLA monitor on every pass."""

    def __init__(self, uow: UnitOfWork, clock: Clock, bus: EventBus) -> None:
        self._uow = uow
        self._clock = clock
        self._bus = bus

    def includes_p2(self) -> bool:
        return self._uow.settings.get(INCLUDE_P2_SETTING) == "true"

    def set_include_p2(self, enabled: bool, actor: User) -> None:
        if not actor.has_permission(Permission.MANAGE_CONFIGURATION):
            raise UnauthorizedOperationError("Only administrators can change escalation settings")
        self._uow.settings.set(INCLUDE_P2_SETTING, "true" if enabled else "false")
        self._bus.publish(
            AdministrativeChange(
                occurred_at=self._clock.now(),
                actor_id=actor.id,
                change="SETTING_CHANGED",
                summary=f"Escalation for P2 incidents {'enabled' if enabled else 'disabled'}",
            )
        )
        self._uow.commit()

    def policy(self) -> EscalationPolicy:
        priorities = {Priority.P1, Priority.P2} if self.includes_p2() else {Priority.P1}
        return EscalationPolicy(frozenset(priorities))

    def apply(self, incident: Incident, now: datetime, policy: EscalationPolicy) -> int:
        """Escalate step by step (each level audited + notified). Returns steps taken."""
        steps = policy.pending_steps(incident, now)
        for step in steps:
            incident.escalate(
                level=step.level, level_name=step.name, recipient_ids=tuple(self._recipients(step, incident)), now=now
            )
        return len(steps)

    def _recipients(self, step: EscalationStep, incident: Incident) -> list[int]:
        users = self._uow.users
        admins = [a for a in users.list_administrators() if a.is_active]
        system_admins = [a.id for a in admins if a.admin_level is AdminLevel.SYSTEM_ADMIN]
        match step.level:
            case 1:
                return [incident.assigned_technician_id] if incident.assigned_technician_id else system_admins
            case 2:
                return self._team_leads(incident)
            case 3:
                return system_admins
            case _:
                return [a.id for a in admins if a.admin_level is AdminLevel.IT_MANAGER]

    def _team_leads(self, incident: Incident) -> list[int]:
        leads = [t for t in self._uow.users.list_technicians() if t.is_active and t.profile.is_team_lead]
        assignee = self._uow.users.get(incident.assigned_technician_id) if incident.assigned_technician_id else None
        if isinstance(assignee, Technician):
            same_team = [t.id for t in leads if t.profile.team == assignee.profile.team and t.id != assignee.id]
            if same_team:
                return same_team
        return [t.id for t in leads if t.id != incident.assigned_technician_id]
