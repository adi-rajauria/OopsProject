"""Shared fixtures: an in-memory 'world' with services, categories, SLA policies
and users, wired exactly like production except for the clock and storage."""

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

os.environ.setdefault("ITSM_JWT_SECRET", "test-secret-key-that-is-at-least-32-characters-long")

from app.core.security import JwtTokenService  # noqa: E402
from app.domain.category import Category  # noqa: E402
from app.domain.enums import AdminLevel, Priority, Role  # noqa: E402
from app.domain.factories import NewIncidentData, UserFactory  # noqa: E402
from app.domain.incident import Incident  # noqa: E402
from app.domain.service import ITService  # noqa: E402
from app.domain.sla import SLAPolicy  # noqa: E402
from app.domain.users import Administrator, Employee, Technician, TechnicianProfile, User  # noqa: E402
from app.notifications.channels import ChannelRegistry, EmailChannel, InAppChannel, SMSChannel  # noqa: E402
from app.notifications.providers import FakeSmsGateway, FakeSmtpProvider  # noqa: E402
from app.repositories.memory import InMemoryUnitOfWork  # noqa: E402
from app.services.container import Infrastructure, ServiceContainer, build_container  # noqa: E402

START = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)

# PDF example table: priority -> (response minutes, resolution minutes)
PDF_SLA = {Priority.P1: (5, 30), Priority.P2: (15, 120), Priority.P3: (60, 480), Priority.P4: (240, 1440)}


class FakeClock:
    def __init__(self, start: datetime = START) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, **delta: float) -> datetime:
        self._now += timedelta(**delta)
        return self._now


class PlainHasher:
    """Fast stand-in for Argon2 in service tests (Argon2 itself is tested in test_auth)."""

    def hash(self, password: str) -> str:
        return f"plain${password}"

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == f"plain${password}"


@dataclass
class World:
    uow: InMemoryUnitOfWork
    clock: FakeClock
    container: ServiceContainer
    smtp: FakeSmtpProvider
    sms: FakeSmsGateway
    services: dict[str, ITService] = field(default_factory=dict)
    categories: dict[str, Category] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)

    @property
    def employee(self) -> Employee:
        return self.users["employee"]

    @property
    def admin(self) -> Administrator:
        return self.users["admin"]

    def tech(self, key: str) -> Technician:
        return self.users[key]

    def report(self, reporter: User | None = None, **overrides) -> Incident:
        data = dict(title="Payment application unavailable",
                    description="Users are unable to complete transactions on the payment portal.",
                    service_id=self.services["PAY"].id, impact=4, urgency=4, affected_users=50,
                    category_id=self.categories["APPLICATION"].id)
        data.update(overrides)
        return self.container.incidents.report(reporter or self.employee, NewIncidentData(**data))


def _user(uow: InMemoryUnitOfWork, role: Role, email: str, name: str, **extra) -> User:
    user = UserFactory.create(role, email=email, full_name=name, password_hash="plain$Password1",
                              created_at=START, **extra)
    return uow.users.add(user)


def build_world(clock: FakeClock | None = None) -> World:
    clock = clock or FakeClock()
    uow = InMemoryUnitOfWork()
    smtp, sms = FakeSmtpProvider(), FakeSmsGateway()
    infra = Infrastructure(
        clock=clock, hasher=PlainHasher(),
        tokens=JwtTokenService(os.environ["ITSM_JWT_SECRET"], clock),
        channels=ChannelRegistry([InAppChannel(), EmailChannel(smtp), SMSChannel(sms)]),
    )
    world = World(uow=uow, clock=clock, container=build_container(uow, infra), smtp=smtp, sms=sms)

    for code, name, crit in (("PAY", "Payments", 4), ("MAIL", "Email", 3), ("WIKI", "Intranet Wiki", 1)):
        world.services[code] = uow.services.add(ITService(id=None, code=code, name=name,
                                                          business_criticality=crit))
    for code, keywords in (("APPLICATION", ["app", "error"]), ("NETWORK", ["vpn", "wifi"]),
                           ("DATABASE", ["sql", "query"]), ("HARDWARE", ["laptop", "printer"])):
        world.categories[code] = uow.categories.add(Category(id=None, code=code, name=code.title(),
                                                             keywords=keywords))
    for priority, (response, resolution) in PDF_SLA.items():
        uow.sla_policies.add(SLAPolicy(id=None, priority=priority, response_minutes=response,
                                       resolution_minutes=resolution))

    world.users["employee"] = _user(uow, Role.EMPLOYEE, "emp@corp.test", "Eve Employee", phone="+91 9000000001")
    world.users["employee2"] = _user(uow, Role.EMPLOYEE, "emp2@corp.test", "Evan Employee")
    world.users["t_app"] = _user(uow, Role.TECHNICIAN, "app@corp.test", "Asha AppTech", phone="+91 9000000002",
                                 profile=TechnicianProfile(skills=frozenset({"APPLICATION"}), experience_years=5))
    world.users["t_net"] = _user(uow, Role.TECHNICIAN, "net@corp.test", "Nikhil NetTech",
                                 profile=TechnicianProfile(skills=frozenset({"NETWORK"}), experience_years=10))
    world.users["t_db"] = _user(uow, Role.TECHNICIAN, "db@corp.test", "Dia DbTech",
                                profile=TechnicianProfile(skills=frozenset({"DATABASE", "APPLICATION"}),
                                                          experience_years=2))
    world.users["admin"] = _user(uow, Role.ADMINISTRATOR, "admin@corp.test", "Ada Admin", phone="+91 9000000003")
    world.users["manager"] = _user(uow, Role.ADMINISTRATOR, "manager@corp.test", "Mani Manager",
                                   admin_level=AdminLevel.IT_MANAGER)
    return world


@pytest.fixture
def world() -> World:
    return build_world()
