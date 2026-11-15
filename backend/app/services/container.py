"""Composition root for one unit of work: wires observers onto a fresh EventBus
and builds the services. Dependency injection by constructor everywhere."""

from dataclasses import dataclass

from app.domain.clock import Clock
from app.domain.events import EventBus, EventObserver
from app.domain.repositories import UnitOfWork
from app.domain.strategies.channel_selection import ChannelSelectionPolicy, DefaultChannelSelectionPolicy
from app.domain.strategies.priority import PriorityCalculator, WeightedPriorityCalculator
from app.notifications.channels import ChannelRegistry
from app.observers.audit_logger import AuditLogger
from app.observers.notification_dispatcher import NotificationDispatcher
from app.observers.sla_tracker import SLATracker
from app.services.assignment_service import AssignmentService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.incident_service import IncidentService
from app.services.notification_service import NotificationService
from app.services.ports import PasswordHasher, TokenService
from app.services.sla_service import SLAService


@dataclass(frozen=True)
class Infrastructure:
    """Long-lived, stateless collaborators shared by every request."""

    clock: Clock
    hasher: PasswordHasher
    tokens: TokenService
    channels: ChannelRegistry
    channel_policy: ChannelSelectionPolicy = DefaultChannelSelectionPolicy()
    priority_calculator: PriorityCalculator = WeightedPriorityCalculator()
    extra_observers: tuple[EventObserver, ...] = ()


@dataclass(frozen=True)
class ServiceContainer:
    uow: UnitOfWork
    bus: EventBus
    auth: AuthService
    incidents: IncidentService
    assignment: AssignmentService
    sla: SLAService
    notifications: NotificationService
    audit: AuditService


def build_container(uow: UnitOfWork, infra: Infrastructure) -> ServiceContainer:
    bus = EventBus()
    bus.attach(AuditLogger(uow))
    bus.attach(SLATracker(uow))
    bus.attach(NotificationDispatcher(uow, infra.channels, infra.channel_policy))
    for observer in infra.extra_observers:
        bus.attach(observer)
    assignment = AssignmentService(uow, infra.clock, bus)
    sla = SLAService(uow, infra.clock, bus)
    return ServiceContainer(
        uow=uow,
        bus=bus,
        auth=AuthService(uow, infra.hasher, infra.tokens, infra.clock, bus),
        incidents=IncidentService(uow, infra.clock, bus, infra.priority_calculator, assignment, sla),
        assignment=assignment,
        sla=sla,
        notifications=NotificationService(uow),
        audit=AuditService(uow),
    )
