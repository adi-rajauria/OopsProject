"""Composition root for one unit of work: wires observers onto a fresh EventBus
and builds the services. Dependency injection by constructor everywhere."""

from dataclasses import dataclass, field

from app.domain.clock import Clock
from app.domain.events import EventBus, EventObserver
from app.domain.repositories import UnitOfWork
from app.domain.strategies.channel_selection import ChannelSelectionPolicy, DefaultChannelSelectionPolicy
from app.domain.strategies.priority import PriorityCalculator, WeightedPriorityCalculator
from app.intelligence.text_similarity import TextSimilarity, TfidfTextSimilarity
from app.notifications.channels import ChannelRegistry
from app.observers.audit_logger import AuditLogger
from app.observers.notification_dispatcher import NotificationDispatcher
from app.observers.realtime_forwarder import RealtimeForwarder
from app.observers.sla_tracker import SLATracker
from app.realtime.broadcaster import EventBroadcaster
from app.services.admin_service import AdminService
from app.services.assignment_service import AssignmentService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.escalation_service import EscalationService
from app.services.incident_service import IncidentService
from app.services.intelligence_service import IntelligenceService
from app.services.notification_service import NotificationService
from app.services.ports import PasswordHasher, TokenService
from app.services.report_service import ReportService
from app.services.search_service import SearchService
from app.services.sla_service import SLAService


@dataclass(frozen=True)
class Infrastructure:
    """Long-lived, stateless (or thread-safe) collaborators shared by every request."""

    clock: Clock
    hasher: PasswordHasher
    tokens: TokenService
    channels: ChannelRegistry
    channel_policy: ChannelSelectionPolicy = field(default_factory=DefaultChannelSelectionPolicy)
    priority_calculator: PriorityCalculator = field(default_factory=WeightedPriorityCalculator)
    similarity: TextSimilarity = field(default_factory=TfidfTextSimilarity)
    broadcaster: EventBroadcaster | None = None
    extra_observers: tuple[EventObserver, ...] = ()


@dataclass(frozen=True)
class ServiceContainer:
    uow: UnitOfWork
    clock: Clock
    bus: EventBus
    auth: AuthService
    incidents: IncidentService
    assignment: AssignmentService
    sla: SLAService
    escalation: EscalationService
    intelligence: IntelligenceService
    search: SearchService
    reports: ReportService
    admin: AdminService
    notifications: NotificationService
    audit: AuditService


def build_event_bus(uow: UnitOfWork, infra: Infrastructure) -> EventBus:
    bus = EventBus()
    bus.attach(AuditLogger(uow))
    bus.attach(SLATracker(uow))
    bus.attach(NotificationDispatcher(uow, infra.channels, infra.channel_policy))
    if infra.broadcaster is not None:
        bus.attach(RealtimeForwarder(uow, infra.broadcaster))
    for observer in infra.extra_observers:
        bus.attach(observer)
    return bus


def build_container(uow: UnitOfWork, infra: Infrastructure) -> ServiceContainer:
    clock = infra.clock
    bus = build_event_bus(uow, infra)
    auth = AuthService(uow, infra.hasher, infra.tokens, clock, bus)
    assignment = AssignmentService(uow, clock, bus)
    escalation = EscalationService(uow, clock, bus)
    sla = SLAService(uow, clock, bus, escalation)
    intelligence = IntelligenceService(uow, clock, infra.similarity, assignment)
    return ServiceContainer(
        uow=uow,
        clock=clock,
        bus=bus,
        auth=auth,
        incidents=IncidentService(uow, clock, bus, infra.priority_calculator, assignment, sla, intelligence),
        assignment=assignment,
        sla=sla,
        escalation=escalation,
        intelligence=intelligence,
        search=SearchService(uow),
        reports=ReportService(uow, clock),
        admin=AdminService(uow, clock, bus, auth),
        notifications=NotificationService(uow),
        audit=AuditService(uow),
    )
