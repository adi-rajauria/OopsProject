"""The SQLAlchemy repositories must behave exactly like the in-memory ones (run on SQLite)."""

from datetime import timedelta

import pytest

from app.domain.category import Category
from app.domain.clock import ensure_utc
from app.domain.enums import IncidentStatus, Priority, Role, SLATarget
from app.domain.exceptions import PersistenceError
from app.domain.factories import NewIncidentData, UserFactory
from app.domain.service import ITService
from app.domain.sla import SLAPolicy
from app.domain.users import Technician, TechnicianProfile
from app.main import build_infrastructure
from app.repositories.orm import IncidentRow
from app.repositories.sql_repositories import SqlAlchemyUnitOfWork
from app.services.container import build_container
from tests.conftest import PDF_SLA, START


def seed(uow: SqlAlchemyUnitOfWork):
    pay = uow.services.add(ITService(id=None, code="PAY", name="Payments", business_criticality=4))
    gateway = uow.services.add(ITService(id=None, code="GW", name="API Gateway", business_criticality=4))
    pay.set_dependencies({gateway.id})
    uow.services.update(pay)
    app_cat = uow.categories.add(Category(id=None, code="APPLICATION", name="Application", keywords=["app"]))
    for priority, (response, resolution) in PDF_SLA.items():
        uow.sla_policies.add(
            SLAPolicy(id=None, priority=priority, response_minutes=response, resolution_minutes=resolution)
        )
    employee = uow.users.add(
        UserFactory.create(Role.EMPLOYEE, email="e@corp.test", full_name="Emp One", password_hash="h", created_at=START)
    )
    tech = uow.users.add(
        UserFactory.create(
            Role.TECHNICIAN,
            email="t@corp.test",
            full_name="Tech One",
            password_hash="h",
            created_at=START,
            phone="+91 9000000009",
            profile=TechnicianProfile(skills=frozenset({"APPLICATION"}), experience_years=4),
        )
    )
    uow.users.add(
        UserFactory.create(
            Role.ADMINISTRATOR, email="a@corp.test", full_name="Admin One", password_hash="h", created_at=START
        )
    )
    uow.commit()
    return pay, app_cat, employee, tech


def test_incident_round_trips_through_postgres_compatible_schema(settings, session_factory, clock):
    infra = build_infrastructure(settings, clock)
    with session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session, clock)
        pay, category, employee, tech = seed(uow)
        container = build_container(uow, infra)
        incident = container.incidents.report(
            employee,
            NewIncidentData(
                title="Payment application unavailable",
                description="Checkout fails with HTTP 503 for all users",
                service_id=pay.id,
                impact=4,
                urgency=4,
                affected_users=200,
                category_id=category.id,
            ),
        )
        clock.advance(minutes=2)
        container.incidents.acknowledge(incident.id, tech)
        container.incidents.start_work(incident.id, tech)
        container.incidents.add_comment(incident.id, tech, "Investigating gateway", internal=True)
        clock.advance(minutes=40)
        container.sla.run_checks()
        incident_id = incident.id

    with session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session, clock)
        loaded = uow.incidents.get(incident_id)
        assert loaded.status is IncidentStatus.IN_PROGRESS and loaded.priority is Priority.P1
        assert loaded.assigned_technician_id == tech.id
        assert loaded.acknowledged_at == START + timedelta(minutes=2)
        assert loaded.sla.is_breached(SLATarget.RESOLUTION) and not loaded.sla.is_breached(SLATarget.RESPONSE)
        assert [(c.body, c.is_internal) for c in loaded.comments] == [("Investigating gateway", True)]
        assert uow.audit.trail_for(incident_id).actions()[:4] == [
            "CREATED",
            "CLASSIFIED",
            "PRIORITY_CALCULATED",
            "ASSIGNED",
        ]
        assert [v.target for v in uow.sla_violations.list()] == [SLATarget.RESOLUTION]
        assert uow.incidents.active_counts_by_technician() == {tech.id: 1}
        assert uow.services.get(pay.id).depends_on == {pay.id + 1}
        reloaded_tech = uow.users.get(tech.id)
        assert isinstance(reloaded_tech, Technician) and reloaded_tech.has_skill("application")
        assert len(uow.notifications.list_for_user(tech.id)) >= 2


def test_database_failure_is_reported_as_persistence_error(session_factory, clock):
    with session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session, clock)
        uow.services.add(ITService(id=None, code="DUP", name="First", business_criticality=2))
        with pytest.raises(PersistenceError):
            uow.services.add(ITService(id=None, code="DUP", name="Second", business_criticality=2))


def test_paused_sla_clock_is_persisted(settings, session_factory, clock):
    infra = build_infrastructure(settings, clock)
    with session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session, clock)
        pay, category, employee, tech = seed(uow)
        incidents = build_container(uow, infra).incidents
        incident = incidents.report(
            employee,
            NewIncidentData(
                title="Refunds stuck",
                description="Refund requests stay pending for every customer",
                service_id=pay.id,
                impact=4,
                urgency=4,
                affected_users=20,
                category_id=category.id,
            ),
        )
        incidents.acknowledge(incident.id, tech)
        incidents.start_work(incident.id, tech)
        incidents.request_info(incident.id, tech, "Which order ids are affected?")
        incident_id = incident.id

    with session_factory() as session:
        loaded = SqlAlchemyUnitOfWork(session, clock).incidents.get(incident_id)
        assert loaded.sla.is_paused and loaded.sla.paused_at == START

    clock.advance(minutes=20)
    with session_factory() as session:
        uow = SqlAlchemyUnitOfWork(session, clock)
        build_container(uow, infra).incidents.provide_info(incident_id, employee, "Orders 1001 to 1050")

    with session_factory() as session:
        loaded = SqlAlchemyUnitOfWork(session, clock).incidents.get(incident_id)
        assert not loaded.sla.is_paused and loaded.sla.paused_seconds == 20 * 60
        assert loaded.sla.resolution_due_at == START + timedelta(minutes=50)
        row_due = session.get(IncidentRow, incident_id).resolution_due_at
        assert ensure_utc(row_due) == START + timedelta(minutes=50)
