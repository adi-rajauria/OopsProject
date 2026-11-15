from dataclasses import dataclass

from app.domain.clock import Clock
from app.domain.enums import Permission
from app.domain.events import EventBus, SettingChanged
from app.domain.exceptions import (
    TechnicianUnavailableError,
    TechnicianWorkloadExceededError,
    UnauthorizedOperationError,
    UserNotFoundError,
)
from app.domain.incident import Incident
from app.domain.repositories import UnitOfWork
from app.domain.strategies.assignment import (
    DEFAULT_STRATEGY_KEY,
    AssignmentContext,
    AssignmentDecision,
    AssignmentStrategy,
    AssignmentStrategyRegistry,
    TechnicianCandidate,
)
from app.domain.users import Technician, User

STRATEGY_SETTING = "assignment.strategy"
LAST_ASSIGNED_SETTING = "assignment.last_technician_id"


@dataclass(frozen=True)
class StrategyInfo:
    key: str
    name: str
    description: str
    active: bool


@dataclass(frozen=True)
class WorkloadEntry:
    technician: Technician
    active_incidents: int

    @property
    def utilisation_pct(self) -> int:
        return round(100 * self.active_incidents / self.technician.profile.max_workload)


class AssignmentService:
    """Applies the *currently configured* strategy. The strategy is looked up from
    settings on every call, so an admin can switch it at runtime."""

    def __init__(self, uow: UnitOfWork, clock: Clock, bus: EventBus) -> None:
        self._uow = uow
        self._clock = clock
        self._bus = bus

    # --- configuration ----------------------------------------------------------------
    def active_strategy_key(self) -> str:
        key = self._uow.settings.get(STRATEGY_SETTING) or DEFAULT_STRATEGY_KEY
        return key if AssignmentStrategyRegistry.is_registered(key) else DEFAULT_STRATEGY_KEY

    def active_strategy(self) -> AssignmentStrategy:
        return AssignmentStrategyRegistry.create(self.active_strategy_key())

    def list_strategies(self) -> list[StrategyInfo]:
        active = self.active_strategy_key()
        return [StrategyInfo(s.key, s.name, s.description, s.key == active)
                for s in AssignmentStrategyRegistry.available()]

    def set_strategy(self, key: str, actor: User) -> None:
        if not actor.has_permission(Permission.MANAGE_CONFIGURATION):
            raise UnauthorizedOperationError("Only administrators can change the assignment strategy")
        AssignmentStrategyRegistry.create(key)  # validates the key
        old = self.active_strategy_key()
        self._uow.settings.set(STRATEGY_SETTING, key)
        self._bus.publish(SettingChanged(occurred_at=self._clock.now(), actor_id=actor.id,
                                         key=STRATEGY_SETTING, old_value=old, new_value=key))
        self._uow.commit()

    # --- workload ---------------------------------------------------------------------
    def workload(self) -> list[WorkloadEntry]:
        counts = self._uow.incidents.active_counts_by_technician()
        return [WorkloadEntry(t, counts.get(t.id, 0)) for t in self._uow.users.list_technicians() if t.is_active]

    def candidates_for(self, incident: Incident) -> list[TechnicianCandidate]:
        counts = self._uow.incidents.active_counts_by_technician()
        history = self._uow.incidents.resolved_counts_for_service(incident.service_id)
        return [TechnicianCandidate(t, counts.get(t.id, 0), history.get(t.id, 0))
                for t in self._uow.users.list_technicians()
                if t.is_active and t.id != incident.assigned_technician_id]

    # --- assignment -------------------------------------------------------------------
    def auto_assign(self, incident: Incident) -> AssignmentDecision:
        """Raises TechnicianUnavailableError when nobody is eligible (incident stays CLASSIFIED)."""
        category = self._uow.categories.get(incident.category_id) if incident.category_id else None
        last = self._uow.settings.get(LAST_ASSIGNED_SETTING)
        context = AssignmentContext(
            service_id=incident.service_id, category_code=category.code if category else None,
            priority=incident.priority, last_assigned_technician_id=int(last) if last else None,
        )
        decision = self.active_strategy().choose(self.candidates_for(incident), context)
        incident.assign(decision.technician, actor=None, reason=decision.reason, now=self._clock.now())
        self._uow.settings.set(LAST_ASSIGNED_SETTING, str(decision.technician.id))
        return decision

    def manual_assign(self, incident: Incident, technician_id: int, actor: User) -> Technician:
        if not actor.has_permission(Permission.ASSIGN_INCIDENTS):
            raise UnauthorizedOperationError("Only administrators can assign incidents")
        technician = self._uow.users.get(technician_id)
        if not isinstance(technician, Technician):
            raise UserNotFoundError(technician_id)
        if not technician.is_active or not technician.profile.is_available:
            raise TechnicianUnavailableError(f"{technician.full_name} is not available for new incidents")
        active = self._uow.incidents.active_counts_by_technician().get(technician.id, 0)
        if active >= technician.profile.max_workload:
            raise TechnicianWorkloadExceededError(technician.full_name, active, technician.profile.max_workload)
        incident.assign(technician, actor=actor, reason=f"manual assignment by {actor.full_name}",
                        now=self._clock.now())
        return technician
