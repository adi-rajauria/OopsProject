"""End-to-end business flows through the services (in-memory repositories, no DB)."""

from datetime import timedelta

import pytest

from app.domain.enums import ChannelType, IncidentStatus, NotificationType, Priority, SLAStatus, SLATarget
from app.domain.exceptions import (
    FeedbackAlreadySubmittedError,
    IncidentNotFoundError,
    InvalidInputError,
    InvalidStateTransitionError,
    MissingSLAConfigurationError,
    ServiceNotFoundError,
    TechnicianUnavailableError,
    TechnicianWorkloadExceededError,
    UnauthorizedOperationError,
)
from tests.conftest import START


def notifications_for(world, user, channel=None):
    return [(n.type, n.channel) for n in world.uow.notifications.list_all()
            if n.recipient_id == user.id and (channel is None or n.channel == channel)]


def work_to_resolved(world, incident):
    svc, tech = world.container.incidents, world.tech("t_app")
    svc.acknowledge(incident.id, tech)
    svc.start_work(incident.id, tech)
    return svc.resolve(incident.id, tech, "Restarted the payment gateway pods and cleared the queue.")


def test_report_classifies_prioritises_applies_sla_and_assigns(world):
    incident = world.report()

    assert incident.number == "INC1001"
    assert incident.status is IncidentStatus.ASSIGNED
    assert incident.priority is Priority.P1 and incident.priority_score == 64
    assert incident.sla.response_due_at == START + timedelta(minutes=5)
    assert incident.sla.resolution_due_at == START + timedelta(minutes=30)
    assert incident.assigned_technician_id == world.tech("t_app").id  # skilled, more experienced than t_db

    trail = world.uow.audit.trail_for(incident.id)
    assert trail.actions() == ["CREATED", "CLASSIFIED", "PRIORITY_CALCULATED", "ASSIGNED"]
    assert [r.description for r in trail][0] == "INC1001 created by Employee E1: Payment application unavailable"

    tech_msgs = notifications_for(world, world.tech("t_app"))
    assert {c for t, c in tech_msgs if t is NotificationType.INCIDENT_ASSIGNED} == {
        ChannelType.IN_APP, ChannelType.EMAIL, ChannelType.SMS}  # P1 => SMS as well
    assert (NotificationType.TECHNICIAN_ASSIGNED, ChannelType.EMAIL) in notifications_for(world, world.employee)
    assert world.smtp.outbox and world.sms.sent


def test_full_lifecycle_with_info_request_feedback_and_closure(world):
    svc, tech, emp = world.container.incidents, world.tech("t_app"), world.employee
    incident = world.report()
    svc.acknowledge(incident.id, tech)
    svc.start_work(incident.id, tech)
    svc.add_comment(incident.id, tech, "Checked gateway logs, seeing TLS errors")
    svc.request_info(incident.id, tech, "Which browser were you using?")
    assert svc.get(incident.id, emp).status is IncidentStatus.PENDING_INFO
    svc.provide_info(incident.id, emp, "Chrome 140 on Windows")
    svc.resolve(incident.id, tech, "Renewed the expired TLS certificate on the gateway.")
    svc.verify(incident.id, emp, rating=4, comment="Quick fix, thanks")
    closed = svc.close(incident.id, tech, "Confirmed by reporter")

    assert closed.status is IncidentStatus.CLOSED and closed.closed_at is not None
    assert world.uow.feedback.get_for_incident(incident.id).rating == 4
    states = [(r.previous_state, r.new_state) for r in world.uow.audit.trail_for(incident.id).state_changes()]
    assert states == [(None, "NEW"), ("NEW", "CLASSIFIED"), ("CLASSIFIED", "ASSIGNED"),
                      ("ASSIGNED", "ACKNOWLEDGED"), ("ACKNOWLEDGED", "IN_PROGRESS"),
                      ("IN_PROGRESS", "PENDING_INFO"), ("PENDING_INFO", "IN_PROGRESS"),
                      ("IN_PROGRESS", "RESOLVED"), ("RESOLVED", "VERIFIED"), ("VERIFIED", "CLOSED")]
    employee_types = {t for t, _ in notifications_for(world, emp)}
    assert {NotificationType.INFO_REQUESTED, NotificationType.INCIDENT_RESOLVED,
            NotificationType.INCIDENT_CLOSED} <= employee_types
    assert [c.kind.value for c in closed.comments] == ["NOTE", "INFO_REQUEST", "INFO_REPLY", "RESOLUTION"]


def test_role_and_ownership_rules_are_enforced(world):
    svc = world.container.incidents
    incident = world.report()
    with pytest.raises(UnauthorizedOperationError):
        svc.acknowledge(incident.id, world.employee)  # employee cannot act as technician
    with pytest.raises(UnauthorizedOperationError):
        svc.acknowledge(incident.id, world.tech("t_net"))  # not the assignee
    with pytest.raises(UnauthorizedOperationError):
        svc.get(incident.id, world.users["employee2"])  # employees only see their own incidents
    with pytest.raises(UnauthorizedOperationError):
        svc.assign(incident.id, world.tech("t_net").id, world.tech("t_app"))  # only admins assign
    with pytest.raises(IncidentNotFoundError):
        svc.get(999, world.admin)


def test_illegal_transition_through_service_is_rejected(world):
    incident = world.report()
    with pytest.raises(InvalidStateTransitionError):
        world.container.incidents.resolve(incident.id, world.tech("t_app"), "Skipping acknowledgement entirely")


def test_resolved_incident_close_requires_verification_or_admin_override_after_72h(world):
    svc = world.container.incidents
    incident = work_to_resolved(world, world.report())
    with pytest.raises(InvalidStateTransitionError):
        svc.close(incident.id, world.tech("t_app"))
    world.clock.advance(hours=1)
    with pytest.raises(InvalidStateTransitionError):
        svc.close(incident.id, world.admin)
    world.clock.advance(hours=72)
    closed = svc.close(incident.id, world.admin, "Reporter unresponsive")
    assert closed.status is IncidentStatus.CLOSED and "admin override" in closed.closure_notes


def test_reporter_can_reopen_a_resolution(world):
    svc = world.container.incidents
    incident = work_to_resolved(world, world.report())
    reopened = svc.reopen(incident.id, world.employee, "Still failing for card payments")
    assert reopened.status is IncidentStatus.IN_PROGRESS and reopened.resolved_at is None


def test_unavailable_and_overloaded_technicians_cannot_be_assigned(world):
    for key in ("t_app", "t_net", "t_db"):
        world.tech(key).set_availability(False)
    stuck = world.report()
    assert stuck.status is IncidentStatus.CLASSIFIED and stuck.assigned_technician_id is None

    svc = world.container.incidents
    with pytest.raises(TechnicianUnavailableError):
        svc.assign(stuck.id, world.tech("t_net").id, world.admin)

    world.tech("t_net").update_technician_profile(is_available=True, max_workload=1)
    world.report(title="VPN tunnel keeps dropping", category_id=world.categories["NETWORK"].id)
    with pytest.raises(TechnicianWorkloadExceededError):
        svc.assign(stuck.id, world.tech("t_net").id, world.admin)

    world.tech("t_app").set_availability(True)
    assert svc.auto_assign(stuck.id, world.admin).assigned_technician_id == world.tech("t_app").id


def test_unknown_service_and_missing_sla_configuration(world):
    with pytest.raises(ServiceNotFoundError):
        world.report(service_id=999)
    p4_default = next(p for p in world.uow.sla_policies.list() if p.priority is Priority.P4)
    world.uow.sla_policies.delete(p4_default.id)
    with pytest.raises(MissingSLAConfigurationError):
        world.report(service_id=world.services["WIKI"].id, impact=1, urgency=1, affected_users=1)
    assert world.uow.incidents.list_all() == [] and world.uow.audit.list_recent() == []


def test_background_sla_check_warns_then_records_violation_once(world):
    incident = world.report()
    sla = world.container.sla

    world.clock.advance(minutes=4)  # 80 % of the 5-minute response target
    assert (sla.run_checks().warnings, sla.run_checks().violations) == (1, 0)
    assert (NotificationType.SLA_WARNING, ChannelType.IN_APP) in notifications_for(world, world.tech("t_app"))

    world.clock.advance(minutes=2)
    assert sla.run_checks().violations == 1
    assert sla.run_checks().violations == 0  # not re-reported
    [violation] = world.uow.sla_violations.list()
    assert (violation.incident_id, violation.target, violation.overdue_minutes) == (incident.id, SLATarget.RESPONSE, 1)
    assert world.uow.incidents.get(incident.id).sla_status(world.clock.now()) is SLAStatus.BREACHED
    admin_msgs = notifications_for(world, world.admin)
    assert {(NotificationType.SLA_VIOLATED, c) for c in ChannelType} <= set(admin_msgs)
    assert "SLA_VIOLATED" in world.uow.audit.trail_for(incident.id).actions()


def test_late_acknowledgement_is_recorded_as_response_violation(world):
    incident = world.report()
    world.clock.advance(minutes=7)
    world.container.incidents.acknowledge(incident.id, world.tech("t_app"))
    assert [v.target for v in world.uow.sla_violations.list()] == [SLATarget.RESPONSE]


def test_notification_failure_does_not_roll_back_the_incident(world):
    world.smtp.fail = True
    incident = world.report()
    assert incident.status is IncidentStatus.ASSIGNED
    emails = [n for n in world.uow.notifications.list_all() if n.channel is ChannelType.EMAIL]
    assert emails and all(not n.delivered and "Email delivery failed" in n.delivery_error for n in emails)
    in_app = [n for n in world.uow.notifications.list_all() if n.channel is ChannelType.IN_APP]
    assert all(n.delivered for n in in_app)


def test_changing_urgency_recalculates_priority_and_rebases_deadlines(world):
    incident = world.report(service_id=world.services["MAIL"].id, impact=2, urgency=1, affected_users=1)
    assert incident.priority is Priority.P3
    world.clock.advance(minutes=10)
    updated = world.container.incidents.update_details(incident.id, world.employee, urgency=4)
    assert updated.priority is Priority.P2 and updated.priority_score == 24
    assert updated.sla.resolution_due_at == START + timedelta(minutes=120)  # from creation, not from edit
    assert "PRIORITY_CHANGED" in world.uow.audit.trail_for(incident.id).actions()
    assert (NotificationType.PRIORITY_CHANGED, ChannelType.IN_APP) in notifications_for(
        world, world.tech("t_app"))


def test_assignment_strategy_can_be_switched_at_runtime_by_admin_only(world):
    assignment = world.container.assignment
    with pytest.raises(UnauthorizedOperationError):
        assignment.set_strategy("LOAD", world.employee)
    network = world.categories["NETWORK"].id
    assert world.report(category_id=network).assigned_technician_id == world.tech("t_net").id  # SKILL default

    assignment.set_strategy("LOAD", world.admin)
    assert [s.key for s in assignment.list_strategies() if s.active] == ["LOAD"]
    assert world.report(category_id=network).assigned_technician_id == world.tech("t_app").id  # lowest load
    assert world.uow.audit.list_recent(action="SETTING_CHANGED")[0].description.endswith("'SKILL' to 'LOAD'")
    with pytest.raises(InvalidInputError):
        assignment.set_strategy("MAGIC", world.admin)


def test_feedback_rules(world):
    svc = world.container.incidents
    incident = world.report()
    with pytest.raises(InvalidStateTransitionError):
        svc.submit_feedback(incident.id, world.employee, 5)  # not resolved yet
    work_to_resolved(world, incident)
    with pytest.raises(InvalidInputError):
        svc.submit_feedback(incident.id, world.employee, 6)
    svc.submit_feedback(incident.id, world.employee, 5, "Great")
    with pytest.raises(FeedbackAlreadySubmittedError):
        svc.submit_feedback(incident.id, world.employee, 4)


def test_internal_notes_are_hidden_from_the_reporter(world):
    svc, tech = world.container.incidents, world.tech("t_app")
    incident = world.report()
    svc.add_comment(incident.id, tech, "Suspect the vendor's API key leaked", internal=True)
    svc.add_comment(incident.id, tech, "We are investigating")
    with pytest.raises(UnauthorizedOperationError):
        svc.add_comment(incident.id, world.employee, "secret?", internal=True)
    visible = svc.get(incident.id, world.employee).comments_visible_to(world.employee)
    assert [c.body for c in visible] == ["We are investigating"]


def test_technician_workload_view(world):
    world.report()
    world.report(title="Card payments time out", category_id=world.categories["DATABASE"].id)
    load = {w.technician.full_name: w.active_incidents for w in world.container.assignment.workload()}
    assert load == {"Asha AppTech": 1, "Nikhil NetTech": 0, "Dia DbTech": 1}


def test_sla_clock_pauses_while_waiting_for_reporter(world):
    svc, sla, tech = world.container.incidents, world.container.sla, world.tech("t_app")
    incident = world.report()  # P1: resolution due at +30 min
    world.clock.advance(minutes=1)
    svc.acknowledge(incident.id, tech)
    svc.start_work(incident.id, tech)
    world.clock.advance(minutes=9)
    svc.request_info(incident.id, tech, "Does it fail for card and UPI payments?")  # paused at +10

    world.clock.advance(minutes=35)  # +45: original deadline long gone
    assert sla.run_checks().violations == 0
    assert svc.get(incident.id, tech).sla_status(world.clock.now()) is SLAStatus.PAUSED
    resumed = svc.provide_info(incident.id, world.employee, "Both fail with the same error")  # resumed at +45
    assert resumed.sla.resolution_due_at == START + timedelta(minutes=65)

    world.clock.advance(minutes=19)  # +64
    assert sla.run_checks().violations == 0
    world.clock.advance(minutes=2)  # +66
    assert sla.run_checks().violations == 1
    descriptions = [r.description for r in world.uow.audit.trail_for(incident.id)]
    assert any("(SLA clock paused)" in d for d in descriptions)
    assert any("(SLA clock resumed)" in d for d in descriptions)
