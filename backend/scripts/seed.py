"""Seed the database with realistic demo data by *replaying history through the real services*.

Every incident is reported, assigned, worked, resolved... via the same services the API
uses, with a movable clock. An event queue processes all actions (and periodic SLA checks)
in chronological order, so audit trails, notifications, SLA violations, duplicate links and
escalations are genuine outputs of the system.

    cd backend && .venv/bin/python -m scripts.seed --reset
"""

import argparse
import heapq
import itertools
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.db import make_engine, make_session_factory
from app.core.security import Argon2PasswordHasher, JwtTokenService
from app.domain.category import Category
from app.domain.enums import AdminLevel, Priority, Role
from app.domain.factories import NewIncidentData, UserFactory
from app.domain.service import ITService
from app.domain.sla import SLAPolicy
from app.domain.users import TechnicianProfile, User
from app.notifications.channels import ChannelRegistry, EmailChannel, InAppChannel, SMSChannel
from app.notifications.providers import FakeSmsGateway, FakeSmtpProvider
from app.repositories.orm import Base
from app.repositories.sql_repositories import SqlAlchemyUnitOfWork
from app.services.container import Infrastructure, ServiceContainer, build_container

DEMO_PASSWORD = "Demo@1234"
HISTORY_DAYS = 14
CHECK_EVERY = timedelta(hours=3)

CATEGORIES = {
    "HARDWARE": ["laptop", "printer", "monitor", "keyboard", "mouse", "battery", "screen", "docking"],
    "SOFTWARE": ["install", "license", "update", "excel", "office", "teams", "software", "upgrade"],
    "NETWORK": ["network", "vpn", "wifi", "internet", "latency", "dns", "router", "packet", "connection"],
    "DATABASE": ["database", "sql", "query", "deadlock", "replication", "postgres", "table", "index"],
    "CLOUD": ["cloud", "aws", "azure", "kubernetes", "pod", "container", "cluster", "autoscaling"],
    "SECURITY": ["phishing", "malware", "virus", "breach", "suspicious", "firewall", "certificate", "ssl"],
    "AUTHENTICATION": ["login", "password", "sso", "mfa", "otp", "locked", "sign in", "token", "account"],
    "APPLICATION": ["application", "app", "error", "crash", "bug", "page", "checkout", "portal", "500"],
    "STORAGE": ["storage", "disk", "drive", "quota", "backup", "file share", "bucket", "space"],
}

# code, name, criticality, owner team, depends on
SERVICES = [
    ("NET", "Campus Network", 4, "Infra", []),
    ("STORAGE", "Cloud Storage", 3, "Platform", []),
    ("DBCORE", "Core Database Cluster", 4, "Platform", ["STORAGE"]),
    ("GW", "API Gateway", 4, "Platform", ["NET"]),
    ("AUTH", "Single Sign-On", 4, "Identity", ["DBCORE"]),
    ("PAY", "Payments Platform", 4, "Apps", ["GW", "DBCORE", "AUTH"]),
    ("EMAIL", "Email & Calendar", 3, "Infra", ["AUTH", "NET"]),
    ("VPN", "Corporate VPN", 3, "Infra", ["NET"]),
    ("HR", "HR Portal", 2, "Apps", ["AUTH", "DBCORE"]),
    ("WIKI", "Intranet Wiki", 1, "Apps", ["AUTH"]),
    ("ENDPT", "Laptops & Printers", 2, "Infra", []),
]

# key, role, name, email local part, extra
USERS: list[tuple[str, Role, str, str, dict]] = [
    ("abhinandan", Role.ADMINISTRATOR, "Abhinandan Chandak", "abhinandan", {"admin_level": AdminLevel.SYSTEM_ADMIN, "phone": "+91 98000 00001"}),
    ("ops", Role.ADMINISTRATOR, "Omar Siddiqui", "ops", {"admin_level": AdminLevel.SYSTEM_ADMIN, "phone": "+91 98000 00002"}),
    ("manager", Role.ADMINISTRATOR, "Ravi Menon", "manager", {"admin_level": AdminLevel.IT_MANAGER, "phone": "+91 98000 00003"}),
    ("priya", Role.TECHNICIAN, "Priya Nair", "priya", {"phone": "+91 98100 00001", "profile": TechnicianProfile(
        skills=frozenset({"APPLICATION", "SOFTWARE", "DATABASE"}), experience_years=9, is_team_lead=True, team="Apps")}),
    ("arjun", Role.TECHNICIAN, "Arjun Verma", "arjun", {"phone": "+91 98100 00002", "profile": TechnicianProfile(
        skills=frozenset({"APPLICATION", "CLOUD"}), experience_years=4, team="Apps")}),
    ("shrey", Role.TECHNICIAN, "Shrey Bhasker", "shrey", {"phone": "+91 98100 00003", "profile": TechnicianProfile(
        skills=frozenset({"NETWORK", "SECURITY"}), experience_years=12, is_team_lead=True, team="Infra")}),
    ("meera", Role.TECHNICIAN, "Meera Iyer", "meera", {"phone": "+91 98100 00004", "profile": TechnicianProfile(
        skills=frozenset({"NETWORK", "HARDWARE"}), experience_years=3, team="Infra")}),
    ("tom", Role.TECHNICIAN, "Tom D'Souza", "tom", {"profile": TechnicianProfile(
        skills=frozenset({"HARDWARE", "SOFTWARE"}), experience_years=2, team="Infra", max_workload=6)}),
    ("dev", Role.TECHNICIAN, "Dev Malhotra", "dev", {"phone": "+91 98100 00006", "profile": TechnicianProfile(
        skills=frozenset({"DATABASE", "STORAGE", "CLOUD"}), experience_years=6, is_team_lead=True, team="Platform")}),
    ("lina", Role.TECHNICIAN, "Lina Fernandes", "lina", {"profile": TechnicianProfile(
        skills=frozenset({"STORAGE", "CLOUD"}), experience_years=7, team="Platform")}),
    ("sana", Role.TECHNICIAN, "Sana Qureshi", "sana", {"phone": "+91 98100 00008", "profile": TechnicianProfile(
        skills=frozenset({"AUTHENTICATION", "SECURITY"}), experience_years=5, team="Identity")}),
    ("adi", Role.EMPLOYEE, "Adi Rajauria", "adi", {"department": "Finance", "phone": "+91 99000 00001"}),
    ("aman", Role.EMPLOYEE, "Aman Gupta", "aman", {"department": "Sales"}),
    ("neha", Role.EMPLOYEE, "Neha Joshi", "neha", {"department": "HR"}),
    ("vikram", Role.EMPLOYEE, "Vikram Singh", "vikram", {"department": "Operations"}),
    ("zoya", Role.EMPLOYEE, "Zoya Khan", "zoya", {"department": "Marketing"}),
    ("karan", Role.EMPLOYEE, "Karan Mehta", "karan", {"department": "Engineering"}),
    ("isha", Role.EMPLOYEE, "Isha Bose", "isha", {"department": "Customer Support"}),
]
EMAIL_DOMAIN = "decerno.demo"

DEFAULT_SLA = {Priority.P1: (5, 30), Priority.P2: (15, 120), Priority.P3: (60, 480), Priority.P4: (240, 1440)}
SERVICE_SLA = [("PAY", Priority.P1, 3, 20), ("PAY", Priority.P2, 10, 60), ("WIKI", Priority.P3, 120, 720)]

RESOLUTIONS = {
    "HARDWARE": "Replaced the faulty unit from spares and confirmed with the user that it works.",
    "SOFTWARE": "Reinstalled the application with the latest patch and re-applied the licence key.",
    "NETWORK": "Replaced a flapping uplink on the access switch and cleared the stale ARP entries.",
    "DATABASE": "Killed the blocking session, added the missing index and verified query plans.",
    "CLOUD": "Scaled the node pool and fixed the pod memory limits that caused OOM restarts.",
    "SECURITY": "Blocked the sender domain, purged the message from all mailboxes and reset exposed passwords.",
    "AUTHENTICATION": "Renewed the expired SSO signing certificate and cleared the identity provider cache.",
    "APPLICATION": "Rolled back the faulty release and restarted the application pods.",
    "STORAGE": "Expanded the volume, cleaned up old snapshots and re-enabled the backup job.",
}

# Path -> lifecycle steps performed after reporting.
PATHS: dict[str, list[str]] = {
    "assigned": [],
    "unassigned": [],
    "ack": ["ack"],
    "work": ["ack", "start"],
    "pending": ["ack", "start", "request"],
    "resolved": ["ack", "start", "resolve"],
    "verified": ["ack", "start", "resolve", "verify"],
    "closed": ["ack", "start", "resolve", "verify", "close"],
    "closed_info": ["ack", "start", "request", "reply", "resolve", "verify", "close"],
    "reopened": ["ack", "start", "resolve", "reopen"],
}


@dataclass(frozen=True)
class Scenario:
    age_hours: float
    reporter: str
    service: str
    category: str | None  # None = let the system suggest one
    impact: int
    urgency: int
    users: int
    title: str
    description: str
    path: str
    late: bool = False  # resolve after the SLA deadline -> recorded violation


S = Scenario
SCENARIOS: list[Scenario] = [
    # --- two weeks of normal operations ---------------------------------------------------------
    S(330, "aman", "ENDPT", "HARDWARE", 1, 2, 1, "Laptop battery drains in an hour", "My laptop battery goes from 100% to 0 in about an hour even when idle.", "closed"),
    S(320, "neha", "HR", "APPLICATION", 2, 2, 15, "HR portal leave page shows error", "The leave application page shows an error 500 when submitting a request.", "closed"),
    S(300, "vikram", "VPN", "NETWORK", 2, 3, 12, "VPN disconnects every 10 minutes", "Remote staff lose the VPN connection every ten minutes and must reconnect.", "closed", late=True),
    S(290, "zoya", "EMAIL", "SOFTWARE", 1, 2, 1, "Outlook add-in will not install", "The CRM add-in for Outlook fails to install with a licence error.", "closed"),
    S(270, "karan", "DBCORE", "DATABASE", 3, 3, 40, "Reporting query deadlocks nightly", "The nightly reporting job hits a deadlock on the orders table and fails.", "closed_info"),
    S(250, "isha", "AUTH", "AUTHENTICATION", 2, 3, 8, "Users locked out after password change", "After the password change several agents are locked out and OTP never arrives.", "closed"),
    S(240, "adi", "PAY", "APPLICATION", 3, 3, 30, "Refund page throws error on submit", "Submitting a refund on the payments portal throws an application error.", "closed", late=True),
    S(220, "aman", "STORAGE", "STORAGE", 2, 2, 20, "Shared drive quota full", "The sales file share is out of space and nobody can save documents.", "closed"),
    S(200, "neha", "ENDPT", "HARDWARE", 1, 1, 1, "Printer on floor 2 jams constantly", "The HP printer on floor 2 jams on every second page.", "verified"),
    S(190, "vikram", "GW", "CLOUD", 3, 3, 60, "Gateway pods restarting with OOM", "API gateway pods restart repeatedly with out-of-memory errors in the cluster.", "closed", late=True),
    S(170, "zoya", "WIKI", "APPLICATION", 1, 1, 5, "Wiki search returns no results", "Searching the intranet wiki returns no results for any term.", "closed"),
    S(160, "karan", "NET", "NETWORK", 3, 4, 150, "Office wifi drops in building B", "The wifi in building B drops every few minutes for everyone on floors 3-5.", "closed"),
    # recurring problem: the VPN drop-outs (300 h, here, and the open one at 4 h) keep coming back
    S(150, "karan", "VPN", "NETWORK", 2, 3, 15, "VPN keeps disconnecting remote staff", "Remote staff are disconnected from the VPN every few minutes again.", "closed"),
    S(140, "isha", "EMAIL", "SECURITY", 3, 3, 25, "Phishing email impersonating CEO", "Several staff received a suspicious email asking for gift cards, apparently from the CEO.", "closed"),
    S(120, "adi", "HR", "AUTHENTICATION", 1, 2, 1, "Cannot sign in to HR portal", "SSO login to the HR portal loops back to the sign in page.", "closed"),
    S(110, "aman", "ENDPT", None, 1, 2, 1, "External monitor not detected on docking station", "My second monitor is not detected when the laptop is on the docking station.", "verified"),
    S(96, "neha", "DBCORE", "DATABASE", 2, 2, 10, "Slow queries on employee table", "Queries on the employee table take 30 seconds since yesterday.", "closed", late=True),
    S(90, "vikram", "VPN", None, 2, 2, 6, "VPN client update fails", "The VPN client update fails on Windows laptops with an install error.", "resolved"),
    S(80, "zoya", "STORAGE", "STORAGE", 2, 3, 30, "Backup job failed for marketing bucket", "The nightly backup of the marketing storage bucket has failed three nights in a row.", "closed"),
    S(72, "karan", "GW", "CLOUD", 3, 2, 40, "API latency spikes during deploys", "API gateway latency spikes to 5 seconds during every deployment.", "reopened"),
    S(60, "isha", "AUTH", "AUTHENTICATION", 3, 3, 50, "MFA push notifications delayed", "MFA push notifications arrive several minutes late so logins time out.", "closed_info"),
    S(50, "adi", "PAY", "APPLICATION", 3, 2, 20, "Invoice download returns blank PDF", "Downloading an invoice from the payments portal gives a blank PDF.", "verified"),
    S(40, "aman", "EMAIL", "SOFTWARE", 1, 1, 1, "Teams calendar not syncing", "Meetings created in Teams do not show up in my Outlook calendar.", "resolved"),
    S(30, "neha", "HR", "APPLICATION", 2, 3, 40, "Payslip page crashes", "The payslip page crashes with an application error for all HR staff.", "pending"),
    S(26, "vikram", "NET", "NETWORK", 2, 2, 20, "High latency to data centre", "Latency to the data centre is above 200 ms from the operations floor.", "work", late=True),
    S(20, "zoya", "WIKI", None, 1, 1, 3, "Wiki pages load slowly", "Intranet wiki pages take ten seconds to load since this morning.", "ack"),
    S(14, "karan", "DBCORE", "DATABASE", 3, 3, 60, "Replication lag on reporting replica", "The reporting replica of the core database is lagging by 40 minutes.", "work"),
    S(10, "isha", "ENDPT", "HARDWARE", 1, 2, 1, "Keyboard keys not working", "Several keys on my laptop keyboard stopped working.", "unassigned"),
    S(8, "adi", "EMAIL", "SECURITY", 2, 2, 4, "Suspicious login alerts on mailbox", "I received alerts about suspicious logins to my mailbox from another country.", "pending"),
    S(6, "aman", "STORAGE", "STORAGE", 2, 2, 15, "File share permissions reset", "Permissions on the sales file share were reset and people cannot open folders.", "assigned"),
    S(5, "neha", "AUTH", "AUTHENTICATION", 2, 3, 25, "Password reset emails not arriving", "Password reset emails from the SSO portal are not arriving for staff.", "work"),
    S(4, "vikram", "VPN", "NETWORK", 3, 3, 80, "VPN tunnel drops for remote staff", "The VPN tunnel keeps dropping for remote workers across all regions.", "ack", late=True),
    S(3.5, "zoya", "HR", "APPLICATION", 1, 1, 1, "Profile photo upload fails", "Uploading a profile photo in the HR portal does nothing.", "assigned"),
    # --- live incident: payments outage cluster (near-duplicates + correlation) --------------
    S(1.6, "karan", "GW", "CLOUD", 4, 4, 300, "API gateway returning 502 errors", "The API gateway returns 502 Bad Gateway for a large share of requests.", "work"),
    S(1.5, "adi", "PAY", "APPLICATION", 4, 4, 500, "Payment application unavailable", "The payment application is unavailable and users are unable to complete transactions.", "ack"),
    S(1.4, "aman", "PAY", "APPLICATION", 4, 3, 200, "Payment transaction failing", "Payment transactions fail at checkout with an error after entering card details.", "assigned"),
    S(1.3, "isha", "PAY", None, 3, 4, 120, "Unable to make payment", "Customers report they are unable to make a payment on the portal.", "assigned"),
    S(1.2, "neha", "PAY", "APPLICATION", 4, 4, 400, "Payment application is unavailable", "The payment application is unavailable, users cannot complete transactions.", "assigned"),
    S(1.0, "vikram", "AUTH", "AUTHENTICATION", 3, 3, 90, "SSO login very slow", "Sign in through SSO takes over a minute, many logins time out.", "assigned"),
    # --- fresh P1s to show the escalation chain at different levels ---------------------------
    S(0.25, "zoya", "EMAIL", "SECURITY", 4, 4, 300, "Mail server sending spam", "Our mail server is sending thousands of spam messages, possible breach.", "assigned"),
    S(0.17, "karan", "NET", "NETWORK", 4, 4, 600, "Core switch down in data centre", "The core network switch in the data centre is down; multiple floors have no network.", "assigned"),
    S(0.08, "isha", "DBCORE", "DATABASE", 4, 4, 250, "Core database not accepting connections", "The core database cluster refuses new connections; applications report connection errors.", "assigned"),
    S(0.03, "adi", "STORAGE", "STORAGE", 2, 2, 10, "Cannot upload files to cloud storage", "Uploads to the cloud storage bucket fail with an access denied error.", "assigned"),
]
RATINGS = itertools.cycle([5, 4, 5, 3, 4, 5, 2, 4, 5])


class MovableClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def set(self, moment: datetime) -> None:
        self._now = moment


@dataclass
class SeedSummary:
    users: int = 0
    services: int = 0
    categories: int = 0
    incidents: int = 0
    violations: int = 0
    links: int = 0
    escalated: int = 0
    by_status: dict[str, int] = field(default_factory=dict)


class Seeder:
    def __init__(self, session_factory: sessionmaker[Session], now: datetime | None = None) -> None:
        self._now = now or datetime.now(UTC)
        self._clock = MovableClock(self._now - timedelta(days=HISTORY_DAYS + 1))
        settings = get_settings()
        self._infra = Infrastructure(
            clock=self._clock, hasher=Argon2PasswordHasher(),
            tokens=JwtTokenService(settings.jwt_secret.get_secret_value(), self._clock),
            channels=ChannelRegistry([InAppChannel(), EmailChannel(FakeSmtpProvider()), SMSChannel(FakeSmsGateway())]),
        )
        self._session = session_factory()
        self._uow = SqlAlchemyUnitOfWork(self._session, self._clock)
        self._c: ServiceContainer = build_container(self._uow, self._infra)
        self._users: dict[str, User] = {}
        self._services: dict[str, ITService] = {}
        self._categories: dict[str, Category] = {}
        self._queue: list[tuple[datetime, int, Callable[[], None]]] = []
        self._seq = itertools.count()

    # ------------------------------------------------------------------ reference data
    def _reference_data(self) -> None:
        uow, hasher = self._uow, self._infra.hasher
        for code, keywords in CATEGORIES.items():
            self._categories[code] = uow.categories.add(Category(id=None, code=code, name=code.title(), keywords=keywords))
        for code, name, criticality, team, _ in SERVICES:
            self._services[code] = uow.services.add(ITService(id=None, code=code, name=name,
                                                              business_criticality=criticality, owner_team=team))
        for code, *_, depends in SERVICES:
            service = self._services[code]
            service.set_dependencies({self._services[d].id for d in depends})
            uow.services.update(service)
        for priority, (response, resolution) in DEFAULT_SLA.items():
            uow.sla_policies.add(SLAPolicy(id=None, priority=priority, response_minutes=response,
                                           resolution_minutes=resolution))
        for code, priority, response, resolution in SERVICE_SLA:
            uow.sla_policies.add(SLAPolicy(id=None, priority=priority, service_id=self._services[code].id,
                                           response_minutes=response, resolution_minutes=resolution))
        password_hash = hasher.hash(DEMO_PASSWORD)
        for key, role, name, local, extra in USERS:
            user = UserFactory.create(role, email=f"{local}@{EMAIL_DOMAIN}", full_name=name,
                                      password_hash=password_hash, created_at=self._clock.now(), **extra)
            self._users[key] = uow.users.add(user)
        uow.commit()

    # ------------------------------------------------------------------ simulation
    def _at(self, moment: datetime, action: Callable[[], None]) -> None:
        if moment <= self._now:
            heapq.heappush(self._queue, (moment, next(self._seq), action))

    def _user(self, user_id: int) -> User:
        return self._uow.users.get(user_id)

    def _report(self, scenario: Scenario) -> None:
        reporter = self._users[scenario.reporter]
        data = NewIncidentData(
            title=scenario.title, description=scenario.description, service_id=self._services[scenario.service].id,
            impact=scenario.impact, urgency=scenario.urgency, affected_users=scenario.users,
            category_id=self._categories[scenario.category].id if scenario.category else None)
        if scenario.path == "unassigned":
            incident = self._report_with_skilled_staff_away(reporter, data, scenario.category)
        else:
            incident = self._c.incidents.report(reporter, data, force=True)
        self._schedule(incident.id, scenario, list(PATHS[scenario.path]))

    def _report_with_skilled_staff_away(self, reporter: User, data: NewIncidentData, category: str):
        away = [t for t in self._uow.users.list_technicians() if t.has_skill(category) and t.profile.is_available]
        for t in away:
            t.set_availability(False)
            self._uow.users.update(t)
        incident = self._c.incidents.report(reporter, data, force=True)
        for t in away:
            t.set_availability(True)
            self._uow.users.update(t)
        self._uow.commit()
        return incident

    def _schedule(self, incident_id: int, scenario: Scenario, steps: list[str]) -> None:
        if not steps:
            return
        incident = self._uow.incidents.get(incident_id)
        sla, now = incident.sla, self._clock.now()
        step = steps[0]
        delay = {
            "ack": timedelta(minutes=sla.response_minutes * (1.6 if scenario.late and scenario.path in ("ack", "work") else 0.5)),
            "start": timedelta(minutes=4),
            "request": timedelta(minutes=sla.resolution_minutes * 0.15),
            "reply": timedelta(minutes=sla.resolution_minutes * 0.3),
            "verify": timedelta(hours=2),
            "close": timedelta(hours=1),
            "reopen": timedelta(hours=3),
        }.get(step)
        if step == "resolve":
            fraction = 1.4 if scenario.late else 0.7
            moment = incident.created_at + timedelta(minutes=sla.resolution_minutes * fraction,
                                                     seconds=sla.paused_seconds)
            moment = max(moment, now + timedelta(minutes=2))
        else:
            moment = now + delay
        self._at(moment, lambda: self._perform(incident_id, scenario, steps))

    def _perform(self, incident_id: int, scenario: Scenario, steps: list[str]) -> None:
        svc = self._c.incidents
        incident = self._uow.incidents.get(incident_id)
        tech = self._user(incident.assigned_technician_id) if incident.assigned_technician_id else None
        reporter = self._users[scenario.reporter]
        match steps[0]:
            case "ack":
                svc.acknowledge(incident_id, tech)
            case "start":
                svc.start_work(incident_id, tech)
                svc.add_comment(incident_id, tech, f"Investigating: checking logs and recent changes on "
                                                   f"{self._uow.services.get(incident.service_id).name}.", internal=True)
            case "request":
                svc.request_info(incident_id, tech, "Can you share a screenshot and the exact time it happened?")
            case "reply":
                svc.provide_info(incident_id, reporter, "Screenshot attached; it happened at around 10:15 today.")
            case "resolve":
                code = self._uow.categories.get(incident.category_id).code
                svc.resolve(incident_id, tech, RESOLUTIONS[code])
            case "verify":
                svc.verify(incident_id, reporter, rating=next(RATINGS), comment="Thanks for the quick help.")
            case "close":
                closer = tech if incident_id % 3 else self._users["abhinandan"]
                svc.close(incident_id, closer, "Confirmed resolved with the reporter.")
            case "reopen":
                svc.reopen(incident_id, reporter, "The problem came back after a few hours.")
        self._schedule(incident_id, scenario, steps[1:])

    def _sla_check(self) -> None:
        self._c.sla.run_checks()

    # ------------------------------------------------------------------ entry point
    def run(self) -> SeedSummary:
        self._reference_data()
        for scenario in SCENARIOS:
            self._at(self._now - timedelta(hours=scenario.age_hours), lambda s=scenario: self._report(s))
        moment = self._now - timedelta(days=HISTORY_DAYS)
        while moment < self._now:
            self._at(moment, self._sla_check)
            moment += CHECK_EVERY
        while self._queue:
            moment, _, action = heapq.heappop(self._queue)
            self._clock.set(moment)
            action()
        self._clock.set(self._now)
        self._sla_check()
        return self._summary()

    def _summary(self) -> SeedSummary:
        incidents = self._uow.incidents.list_all()
        statuses: dict[str, int] = {}
        for i in incidents:
            statuses[i.status.value] = statuses.get(i.status.value, 0) + 1
        links = sum(len(self._uow.links.list_for(i.id)) for i in incidents) // 2
        summary = SeedSummary(
            users=len(self._uow.users.list()), services=len(self._uow.services.list()),
            categories=len(self._uow.categories.list()), incidents=len(incidents),
            violations=len(self._uow.sla_violations.list(limit=10_000)), links=links,
            escalated=sum(i.escalation_level > 0 for i in incidents), by_status=dict(sorted(statuses.items())))
        self._session.close()
        return summary


def reset_database(engine: Engine) -> None:
    tables = [t.name for t in reversed(Base.metadata.sorted_tables)]
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        else:
            for name in tables:
                conn.execute(text(f"DELETE FROM {name}"))


def has_data(session_factory: sessionmaker[Session]) -> bool:
    with session_factory() as session:
        return session.execute(text("SELECT COUNT(*) FROM users")).scalar_one() > 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Decerno with demo data")
    parser.add_argument("--reset", action="store_true", help="delete ALL existing data first")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    engine = make_engine(get_settings().database_url)
    session_factory = make_session_factory(engine)
    if has_data(session_factory):
        if not args.reset:
            print("Database already has data. Re-run with --reset to wipe it and seed again.")
            return 1
        reset_database(engine)
    summary = Seeder(session_factory).run()
    print(f"Seeded: {summary}")
    print(f"\nAll demo accounts use the password: {DEMO_PASSWORD}")
    for key, role, name, local, extra in USERS:
        level = f" ({extra['admin_level'].value})" if "admin_level" in extra else ""
        lead = " (team lead)" if isinstance(extra.get("profile"), TechnicianProfile) and extra["profile"].is_team_lead else ""
        print(f"  {role.value:<14} {local + '@' + EMAIL_DOMAIN:<20} {name}{level}{lead}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
