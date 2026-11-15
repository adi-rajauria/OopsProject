"""Users (inheritance/polymorphism), factories, event bus, notification adapters."""

import pytest

from app.domain.enums import ChannelType, NotificationType, Permission, Priority, Role
from app.domain.events import EventBus, IncidentEvent, IncidentUpdated, SettingChanged
from app.domain.exceptions import InvalidIncidentError, InvalidInputError, NotificationDeliveryError
from app.domain.factories import IncidentFactory, NewIncidentData, UserFactory
from app.domain.notification import Notification
from app.domain.service import ITService
from app.domain.strategies.channel_selection import DefaultChannelSelectionPolicy
from app.domain.users import Administrator, Employee, Technician
from app.notifications.channels import EmailChannel, SMSChannel
from app.notifications.providers import FakeSmsGateway, FakeSmtpProvider
from tests.conftest import START


def make(role, **extra):
    return UserFactory.create(
        role, id=1, email="Someone@Corp.test", full_name="Some One", password_hash="h", created_at=START, **extra
    )


def test_user_factory_builds_the_right_subclass_and_normalises_email():
    assert isinstance(make(Role.EMPLOYEE), Employee)
    assert isinstance(make(Role.TECHNICIAN), Technician)
    assert isinstance(make("ADMINISTRATOR"), Administrator)
    assert make(Role.EMPLOYEE).email == "someone@corp.test"


def test_permissions_are_polymorphic_and_revoked_when_deactivated():
    employee, technician, admin = make(Role.EMPLOYEE), make(Role.TECHNICIAN), make(Role.ADMINISTRATOR)
    assert not employee.has_permission(Permission.VIEW_ALL_INCIDENTS)
    assert technician.has_permission(Permission.WORK_INCIDENTS)
    assert not technician.has_permission(Permission.MANAGE_USERS)
    assert all(admin.has_permission(p) for p in Permission)
    admin.deactivate()
    assert not admin.has_permission(Permission.MANAGE_USERS)


@pytest.mark.parametrize(
    "kwargs",
    [dict(role="SUPERUSER"), dict(role=Role.EMPLOYEE, email="not-an-email"), dict(role=Role.EMPLOYEE, full_name="x")],
)
def test_invalid_user_input_is_rejected(kwargs):
    base = dict(email="ok@corp.test", full_name="Valid Name", password_hash="h", created_at=START)
    base.update(kwargs)
    role = base.pop("role")
    with pytest.raises(InvalidInputError):
        UserFactory.create(role, **base)


def test_incident_factory_rejects_invalid_incidents():
    reporter = make(Role.EMPLOYEE)
    service = ITService(id=1, code="PAY", name="Payments", business_criticality=4)
    with pytest.raises(InvalidIncidentError):
        IncidentFactory.create(
            reporter,
            NewIncidentData("Hi", "too short title test", 1, 2, 2),
            service,
            suggested_category_id=None,
            now=START,
        )
    service.update(is_active=False)
    with pytest.raises(InvalidIncidentError):
        IncidentFactory.create(
            reporter,
            NewIncidentData("Payment down", "Nobody can pay anything", 1, 2, 2),
            service,
            suggested_category_id=None,
            now=START,
        )


def test_event_bus_dispatches_by_event_class_hierarchy():
    bus, received = EventBus(), []
    bus.subscribe(IncidentEvent, lambda e: received.append(("incident", e.action)))
    bus.subscribe(SettingChanged, lambda e: received.append(("setting", e.action)))
    bus.publish(IncidentUpdated(occurred_at=START, changed_fields=("title",)))
    bus.publish(SettingChanged(occurred_at=START, key="k", old_value=None, new_value="v"))
    assert received == [("incident", "UPDATED"), ("setting", "SETTING_CHANGED")]


def _notification() -> Notification:
    return Notification(
        id=None,
        recipient_id=1,
        channel=ChannelType.EMAIL,
        type=NotificationType.SLA_VIOLATED,
        title="t",
        body="b",
        created_at=START,
    )


def test_adapters_translate_provider_failures_into_notification_delivery_error():
    user = make(Role.EMPLOYEE, phone="+91 9000000000")
    with pytest.raises(NotificationDeliveryError):
        EmailChannel(FakeSmtpProvider(fail=True)).deliver(_notification(), user)
    with pytest.raises(NotificationDeliveryError):
        SMSChannel(FakeSmsGateway(fail=True)).deliver(_notification(), user)
    smtp = FakeSmtpProvider()
    EmailChannel(smtp).deliver(_notification(), user)
    assert smtp.outbox[0]["to"] == ["someone@corp.test"]
    assert not SMSChannel(FakeSmsGateway()).can_reach(make(Role.EMPLOYEE))


def test_channel_policy_uses_sms_only_for_urgent_events():
    policy = DefaultChannelSelectionPolicy()
    assert policy.channels_for(NotificationType.STATUS_CHANGED, Priority.P1) == [ChannelType.IN_APP]
    assert ChannelType.SMS in policy.channels_for(NotificationType.INCIDENT_ASSIGNED, Priority.P1)
    assert ChannelType.SMS not in policy.channels_for(NotificationType.INCIDENT_ASSIGNED, Priority.P3)
    assert policy.channels_for(NotificationType.SLA_VIOLATED, Priority.P4) == [
        ChannelType.IN_APP,
        ChannelType.EMAIL,
        ChannelType.SMS,
    ]
