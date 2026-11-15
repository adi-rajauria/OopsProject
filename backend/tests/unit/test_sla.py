from datetime import timedelta

import pytest

from app.domain.enums import Priority, SLAStatus, SLATarget
from app.domain.exceptions import InvalidInputError, MissingSLAConfigurationError
from app.domain.sla import FindingKind, IncidentSLA, SLAPolicy, SLAPolicyResolver
from tests.conftest import START


def policy(priority=Priority.P1, response=5, resolution=30, service_id=None, pid=1, warn=75):
    return SLAPolicy(
        id=pid,
        priority=priority,
        response_minutes=response,
        resolution_minutes=resolution,
        service_id=service_id,
        warning_threshold_pct=warn,
    )


def test_service_specific_policy_overrides_default():
    default, specific = policy(pid=1), policy(response=2, resolution=20, service_id=7, pid=2)
    assert SLAPolicyResolver.resolve(Priority.P1, 7, [default, specific]) is specific
    assert SLAPolicyResolver.resolve(Priority.P1, 8, [default, specific]) is default


def test_missing_sla_configuration_raises():
    with pytest.raises(MissingSLAConfigurationError):
        SLAPolicyResolver.resolve(Priority.P2, 1, [policy(priority=Priority.P1)])


def test_deadlines_follow_policy_targets():
    clock = IncidentSLA.from_policy(policy(), START)
    assert clock.response_due_at == START + timedelta(minutes=5)
    assert clock.resolution_due_at == START + timedelta(minutes=30)


def test_breach_only_after_the_deadline_has_passed():
    clock = IncidentSLA.from_policy(policy(), START)
    exactly_due = START + timedelta(minutes=5)
    assert [f.kind for f in clock.evaluate(exactly_due)] == [FindingKind.WARNING]  # 100% elapsed, not breached
    assert not clock.is_breached(SLATarget.RESPONSE)
    findings = clock.evaluate(exactly_due + timedelta(seconds=1))
    assert [(f.kind, f.target) for f in findings] == [(FindingKind.BREACH, SLATarget.RESPONSE)]
    assert clock.evaluate(exactly_due + timedelta(minutes=1)) == []  # reported once only
    assert clock.status(exactly_due + timedelta(minutes=1)) is SLAStatus.BREACHED


def test_warning_raised_at_exactly_the_threshold():
    clock = IncidentSLA.from_policy(policy(response=20, resolution=100), START)
    assert clock.evaluate(START + timedelta(minutes=14, seconds=59)) == []
    assert clock.status(START + timedelta(minutes=14)) is SLAStatus.ON_TRACK
    findings = clock.evaluate(START + timedelta(minutes=15))  # 75 %
    assert [(f.kind, f.target) for f in findings] == [(FindingKind.WARNING, SLATarget.RESPONSE)]
    assert clock.status(START + timedelta(minutes=15)) is SLAStatus.AT_RISK


def test_targets_met_in_time_give_met_status_and_late_response_is_a_breach():
    on_time = IncidentSLA.from_policy(policy(), START)
    on_time.mark_responded(START + timedelta(minutes=4))
    on_time.mark_resolved(START + timedelta(minutes=29))
    assert on_time.status(START + timedelta(hours=5)) is SLAStatus.MET

    late = IncidentSLA.from_policy(policy(), START)
    findings = late.mark_responded(START + timedelta(minutes=6))
    assert [(f.kind, f.target, f.overdue_minutes) for f in findings] == [(FindingKind.BREACH, SLATarget.RESPONSE, 1)]


def test_rebasing_keeps_original_start_time():
    clock = IncidentSLA.from_policy(policy(priority=Priority.P3, response=60, resolution=480), START)
    rebased = clock.rebased_on(policy(priority=Priority.P1))
    assert rebased.started_at == START and rebased.resolution_due_at == START + timedelta(minutes=30)


@pytest.mark.parametrize(("response", "resolution", "warn"), [(0, 10, 75), (30, 10, 75), (5, 30, 100)])
def test_invalid_sla_policy_is_rejected(response, resolution, warn):
    with pytest.raises(InvalidInputError):
        policy(response=response, resolution=resolution, warn=warn)


def test_paused_clock_raises_nothing_and_extends_resolution_deadline():
    clock = IncidentSLA.from_policy(policy(), START)  # P1: 5 / 30 min
    clock.mark_responded(START + timedelta(minutes=2))
    assert clock.pause(START + timedelta(minutes=10)) == []
    paused_at = START + timedelta(minutes=40)  # well past the original 30-min deadline
    assert clock.evaluate(paused_at) == [] and clock.status(paused_at) is SLAStatus.PAUSED
    assert clock.elapsed_pct(SLATarget.RESOLUTION, paused_at) == 33.3  # only 10 running minutes count
    clock.resume(paused_at)
    assert clock.paused_seconds == 30 * 60 and not clock.is_paused
    assert clock.resolution_due_at == START + timedelta(minutes=60)
    assert clock.response_due_at == START + timedelta(minutes=5)  # response target never moves
    assert [f.kind for f in clock.evaluate(START + timedelta(minutes=60))] == [FindingKind.WARNING]
    breach = clock.evaluate(START + timedelta(minutes=60, seconds=1))
    assert [(f.kind, f.target) for f in breach] == [(FindingKind.BREACH, SLATarget.RESOLUTION)]


def test_pausing_after_the_deadline_still_reports_the_breach():
    clock = IncidentSLA.from_policy(policy(), START)
    clock.mark_responded(START + timedelta(minutes=2))
    findings = clock.pause(START + timedelta(minutes=31))
    assert [(f.kind, f.target) for f in findings] == [(FindingKind.BREACH, SLATarget.RESOLUTION)]
    assert clock.status(START + timedelta(minutes=50)) is SLAStatus.BREACHED
