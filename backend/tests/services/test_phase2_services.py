"""Phase 2 business flows: duplicates, auto-categorisation, escalation, search, reports, admin, real-time."""

import asyncio
from datetime import timedelta

import pytest

from app.domain.enums import (
    AdminLevel,
    ChannelType,
    IncidentStatus,
    LinkType,
    NotificationType,
    Priority,
    Role,
    SLAStatus,
)
from app.domain.events import IncidentRef, IncidentUpdated
from app.domain.exceptions import (
    ConflictError,
    DuplicateIncidentError,
    InvalidIncidentError,
    InvalidInputError,
    UnauthorizedOperationError,
)
from app.domain.search import SearchCriteria, SortOrder
from app.domain.users import TechnicianProfile
from app.observers.realtime_forwarder import RealtimeForwarder
from app.realtime.broadcaster import EventBroadcaster
from app.repositories.memory import InMemoryUnitOfWork
from app.services.admin_service import NewUserData
from tests.conftest import START

PAYMENT = dict(
    title="Payment application unavailable",
    description="The payment application is unavailable and users cannot complete transactions.",
)


# --- duplicates & categorisation -----------------------------------------------------------------


def test_same_reporter_duplicate_is_blocked_unless_forced(world):
    first = world.report(force=False, **PAYMENT)
    world.clock.advance(minutes=5)
    with pytest.raises(DuplicateIncidentError) as err:
        world.report(force=False, **PAYMENT)
    assert err.value.details["matches"][0]["number"] == first.number
    second = world.report(force=True, **PAYMENT)
    [link] = world.uow.links.list_for(second.id)
    assert (link.related_incident_id, link.link_type) == (first.id, LinkType.DUPLICATE)
    assert second.parent_incident_id == first.id


def test_similar_reports_from_other_people_are_linked_not_blocked(world):
    first = world.report(force=False, **PAYMENT)
    other = world.report(
        world.users["employee2"],
        force=False,
        title="Payment transaction failing",
        description="Payment transactions fail at checkout with an error for everyone.",
    )
    assert other.status is IncidentStatus.ASSIGNED
    [link] = world.uow.links.list_for(first.id)
    assert link.link_type is LinkType.RELATED and link.other(first.id) == other.id
    assert "related to DCN-1001" in world.uow.audit.list_recent(action="RELATED_DETECTED")[0].description


def test_missing_category_is_suggested_or_rejected(world):
    incident = world.report(
        category_id=None,
        title="VPN keeps dropping",
        description="The vpn connection drops every few minutes from home wifi.",
        service_id=world.services["MAIL"].id,
    )
    assert incident.category_id == world.categories["NETWORK"].id == incident.suggested_category_id
    classified = world.uow.audit.list_recent(action="CLASSIFIED")[0].description
    assert "auto-suggested" in classified
    with pytest.raises(InvalidIncidentError):
        world.report(category_id=None, title="Something odd", description="Something odd is happening today.")


# --- escalation chain ----------------------------------------------------------------------------


def test_unacknowledged_p1_walks_the_whole_escalation_chain(world):
    lead = world.tech("t_db")
    lead.update_technician_profile(is_team_lead=True)  # same team ("General") as the assignee
    incident = world.report()  # P1, response due +5 min, assigned to t_app
    sla = world.container.sla
    world.clock.advance(minutes=5)
    assert sla.run_checks().escalations == 0  # exactly at the deadline: not yet
    world.clock.advance(seconds=1)
    assert sla.run_checks().escalations == 1
    world.clock.advance(minutes=15)
    assert sla.run_checks().escalations == 3
    assert sla.run_checks().escalations == 0
    assert world.uow.incidents.get(incident.id).escalation_level == 4

    recipients = {
        t: {
            n.recipient_id
            for n in world.uow.notifications.list_all()
            if n.type is NotificationType.ESCALATED and n.channel is ChannelType.IN_APP and t in n.body
        }
        for t in ("Technician", "Team Lead", "System Administrator", "IT Manager")
    }
    assert recipients == {
        "Technician": {world.tech("t_app").id},
        "Team Lead": {lead.id},
        "System Administrator": {world.admin.id},
        "IT Manager": {world.users["manager"].id},
    }


def test_acknowledged_or_p2_incidents_do_not_escalate_unless_configured(world):
    acked = world.report()
    world.container.incidents.acknowledge(acked.id, world.tech("t_app"))
    p2 = world.report(
        title="Mail delays",
        description="Email delivery is delayed by twenty minutes for all.",
        service_id=world.services["MAIL"].id,
        impact=3,
        urgency=3,
        affected_users=10,
    )
    assert p2.priority is Priority.P2
    world.clock.advance(hours=2)
    assert world.container.sla.run_checks().escalations == 0
    with pytest.raises(UnauthorizedOperationError):
        world.container.escalation.set_include_p2(True, world.tech("t_app"))
    world.container.escalation.set_include_p2(True, world.admin)
    assert world.container.sla.run_checks().escalations == 4
    assert world.uow.incidents.get(acked.id).escalation_level == 0


# --- search ---------------------------------------------------------------------------------------


@pytest.fixture
def searchable(world):
    pay = world.report()  # DCN-1001 P1 APPLICATION PAY, t_app
    world.clock.advance(hours=1)
    mail = world.report(
        world.users["employee2"],
        title="VPN drops for the sales team",
        description="The vpn tunnel drops every hour for the sales team.",
        service_id=world.services["MAIL"].id,
        impact=2,
        urgency=1,
        affected_users=1,
        category_id=world.categories["NETWORK"].id,
    )  # DCN-1002 P3 NETWORK t_net
    world.clock.advance(hours=1)
    for key in ("t_app", "t_net", "t_db"):
        world.tech(key).set_availability(False)
    wiki = world.report(
        title="Wiki search broken",
        description="Wiki search returns nothing for any query.",
        service_id=world.services["WIKI"].id,
        impact=1,
        urgency=1,
        category_id=world.categories["DATABASE"].id,
    )  # DCN-1003 unassigned P4
    world.container.incidents.acknowledge(pay.id, world.tech("t_app"))
    return world, pay, mail, wiki


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        (dict(incident_id=2), [2]),
        (dict(created_from=START + timedelta(minutes=30)), [3, 2]),
        (dict(created_to=START + timedelta(minutes=30)), [1]),
        (dict(statuses=(IncidentStatus.ACKNOWLEDGED,)), [1]),
        (dict(priorities=(Priority.P3, Priority.P4)), [3, 2]),
        (lambda w: dict(category_ids=(w.categories["NETWORK"].id,)), [2]),
        (lambda w: dict(service_ids=(w.services["WIKI"].id,)), [3]),
        (lambda w: dict(technician_id=w.tech("t_net").id), [2]),
        (dict(unassigned_only=True), [3]),
        (dict(sla_statuses=(SLAStatus.BREACHED,)), [1]),  # P1 acknowledged at +2 h -> response breached
        (dict(text="VPN"), [2]),
        (dict(sort=SortOrder.PRIORITY), [1, 2, 3]),
        (dict(sort=SortOrder.OLDEST, page=2, page_size=2), [3]),
    ],
)
def test_every_search_criterion(searchable, criteria, expected):
    world = searchable[0]
    criteria = criteria(world) if callable(criteria) else criteria
    page = world.container.search.search(world.admin, SearchCriteria(**criteria))
    assert [i.id for i in page.items] == expected


def test_employees_only_find_their_own_incidents(searchable):
    world = searchable[0]
    page = world.container.search.search(world.users["employee2"], SearchCriteria())
    assert [i.id for i in page.items] == [2] and page.total == 1
    queue = world.container.search.technician_queue(world.tech("t_app"))
    assert [i.id for i in queue] == [1]


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(page=0),
        dict(page_size=101),
        dict(text="x" * 201),
        dict(created_from=START, created_to=START - timedelta(days=1)),
    ],
)
def test_invalid_search_criteria(kwargs):
    with pytest.raises(InvalidInputError):
        SearchCriteria(**kwargs)


# --- reports ------------------------------------------------------------------------------------


def test_dashboards(searchable):
    world, pay, mail, wiki = searchable
    reports = world.container.reports
    world.container.incidents.start_work(pay.id, world.tech("t_app"))
    world.container.incidents.resolve(pay.id, world.tech("t_app"), "Restarted the payment gateway service.")
    world.container.incidents.verify(pay.id, world.employee, rating=4)

    overview = reports.overview(world.admin)
    assert (overview.total, overview.open, overview.critical_open, overview.unassigned, overview.resolved) == (
        3,
        2,
        0,
        1,
        1,
    )
    assert overview.sla_violations == 2 and overview.avg_rating == 4 and overview.mttr_hours == pytest.approx(2.0)

    workload = {t.name: (t.active, t.resolved_total) for t in reports.technician_workload(world.admin)}
    assert workload["Asha AppTech"] == (0, 1) and workload["Shrey Bhasker"] == (1, 0)
    services = {s.code: (s.total, s.open, s.violations) for s in reports.service_analysis(world.admin)}
    assert services == {"PAY": (1, 0, 2), "MAIL": (1, 1, 0), "WIKI": (1, 1, 0)}
    sla = reports.sla_report(world.admin)
    assert {v.target.value for v in sla.violations} == {"RESPONSE", "RESOLUTION"}
    assert next(c for c in sla.compliance if c.priority == "P1").compliance_pct == 0.0
    assert reports.trends(world.admin, days=1)[0].created == 3
    with pytest.raises(UnauthorizedOperationError):
        reports.overview(world.employee)
    assert reports.technician_workload(world.tech("t_app"))  # technicians may see workload


# --- administration --------------------------------------------------------------------------


def test_admin_manages_users_and_technicians(world):
    admin = world.container.admin
    with pytest.raises(UnauthorizedOperationError):
        admin.create_user(world.employee, NewUserData(Role.TECHNICIAN, "x@corp.test", "New Tech", "Secret123"))
    with pytest.raises(InvalidInputError):
        admin.create_user(
            world.admin,
            NewUserData(
                Role.TECHNICIAN,
                "x@corp.test",
                "New Tech",
                "Secret123",
                profile=TechnicianProfile(skills=frozenset({"KNITTING"})),
            ),
        )
    tech = admin.create_user(
        world.admin,
        NewUserData(
            Role.TECHNICIAN,
            "x@corp.test",
            "New Tech",
            "Secret123",
            profile=TechnicianProfile(skills=frozenset({"network"})),
        ),
    )
    assert tech.has_skill("NETWORK")
    manager = admin.create_user(
        world.admin,
        NewUserData(
            Role.ADMINISTRATOR, "m2@corp.test", "Second Manager", "Secret123", admin_level=AdminLevel.IT_MANAGER
        ),
    )
    assert manager.admin_level is AdminLevel.IT_MANAGER
    admin.update_technician(world.admin, tech.id, max_workload=3, is_team_lead=True)
    assert tech.profile.max_workload == 3 and tech.profile.is_team_lead
    with pytest.raises(InvalidInputError):
        admin.set_user_active(world.admin, world.admin.id, False)
    admin.set_user_active(world.admin, tech.id, False)
    assert not tech.is_active
    actions = [r.action for r in world.uow.audit.list_recent()]
    assert {"USER_CREATED", "TECHNICIAN_UPDATED", "USER_DEACTIVATED"} <= set(actions)


def test_admin_manages_services_categories_and_policies(world):
    admin = world.container.admin
    with pytest.raises(ConflictError):
        admin.create_service(world.admin, code="pay", name="Payments again", business_criticality=2)
    gateway = admin.create_service(world.admin, code="GW", name="API Gateway", business_criticality=4)
    admin.set_dependencies(world.admin, world.services["PAY"].id, {gateway.id})
    with pytest.raises(InvalidInputError):
        admin.set_dependencies(world.admin, gateway.id, {world.services["PAY"].id})  # cycle
    category = admin.create_category(world.admin, code="printing", name="Printing", keywords=["toner"])
    suggestion = world.container.intelligence.suggest_category("Toner empty", "Out of toner on floor 2 printer")
    assert suggestion[0].code == category.code == "PRINTING"
    p1_default = next(p for p in world.uow.sla_policies.list() if p.priority is Priority.P1)
    with pytest.raises(InvalidInputError):
        admin.delete_policy(world.admin, p1_default.id)
    special = admin.create_policy(
        world.admin,
        priority=Priority.P1,
        service_id=world.services["PAY"].id,
        response_minutes=2,
        resolution_minutes=15,
    )
    with pytest.raises(ConflictError):
        admin.create_policy(
            world.admin,
            priority=Priority.P1,
            service_id=world.services["PAY"].id,
            response_minutes=3,
            resolution_minutes=20,
        )
    assert world.report().sla.resolution_minutes == 15  # service-specific policy now applies
    admin.delete_policy(world.admin, special.id)
    assert {
        "SERVICE_CREATED",
        "SERVICE_DEPENDENCIES_CHANGED",
        "CATEGORY_CREATED",
        "SLA_POLICY_CREATED",
        "SLA_POLICY_DELETED",
    } <= {r.action for r in world.uow.audit.list_recent()}


# --- real-time ------------------------------------------------------------------------------------


class RecordingBroadcaster:
    def __init__(self) -> None:
        self.messages: list[tuple[dict, frozenset[int]]] = []

    def publish(self, message: dict, audience: frozenset[int]) -> None:
        self.messages.append((message, audience))


def test_realtime_push_happens_only_after_commit():
    uow, broadcaster = InMemoryUnitOfWork(), RecordingBroadcaster()
    forwarder = RealtimeForwarder(uow, broadcaster)
    ref = IncidentRef(
        id=1,
        number="DCN-1001",
        title="t",
        reporter_id=10,
        assignee_id=20,
        priority=Priority.P2,
        status=IncidentStatus.ASSIGNED,
        service_id=1,
    )
    forwarder.handle(IncidentUpdated(occurred_at=START, changed_fields=("title",), incident=ref))
    assert broadcaster.messages == []
    uow.rollback()
    uow.commit()
    assert broadcaster.messages == []  # rolled-back change is never announced
    forwarder.handle(IncidentUpdated(occurred_at=START, changed_fields=("title",), incident=ref))
    uow.commit()
    [(message, audience)] = broadcaster.messages
    assert message["number"] == "DCN-1001" and audience == {10, 20}


def test_broadcaster_delivers_to_staff_and_involved_users_only():
    async def scenario():
        hub = EventBroadcaster()
        staff, reporter, stranger = hub.subscribe(1, True), hub.subscribe(10, False), hub.subscribe(99, False)
        hub.publish({"n": 1}, frozenset({10}))
        await asyncio.sleep(0)
        sizes = (staff.queue.qsize(), reporter.queue.qsize(), stranger.queue.qsize())
        hub.unsubscribe(staff)
        return sizes, hub.subscriber_count

    assert asyncio.run(scenario()) == ((1, 1, 0), 2)
