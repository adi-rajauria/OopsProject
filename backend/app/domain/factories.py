"""Factory pattern: one place that knows how to build valid Users, Incidents and
Notifications, so callers never pick concrete classes or templates themselves."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import AdminLevel, ChannelType, NotificationType, Permission, Role
from app.domain.events import IncidentRef
from app.domain.exceptions import InvalidIncidentError, InvalidInputError, UnauthorizedOperationError
from app.domain.incident import Incident
from app.domain.notification import Notification
from app.domain.service import ITService
from app.domain.users import Administrator, Employee, Technician, TechnicianProfile, User


class UserFactory:
    @classmethod
    def create(
        cls,
        role: Role | str,
        *,
        email: str,
        full_name: str,
        password_hash: str,
        created_at: datetime,
        id: int | None = None,
        phone: str | None = None,
        department: str | None = None,
        is_active: bool = True,
        profile: TechnicianProfile | None = None,
        admin_level: AdminLevel | None = None,
    ) -> User:
        try:
            role = Role(role)
        except ValueError:
            raise InvalidInputError(f"Unknown role '{role}'", details={"field": "role"}) from None
        common = dict(id=id, email=email, full_name=full_name, password_hash=password_hash,
                      created_at=created_at, phone=phone, department=department, is_active=is_active)
        match role:
            case Role.EMPLOYEE:
                return Employee(**common)
            case Role.TECHNICIAN:
                return Technician(profile=profile, **common)
            case Role.ADMINISTRATOR:
                return Administrator(admin_level=admin_level or AdminLevel.SYSTEM_ADMIN, **common)


@dataclass(frozen=True)
class NewIncidentData:
    title: str
    description: str
    service_id: int
    impact: int
    urgency: int
    affected_users: int = 1
    category_id: int | None = None


class IncidentFactory:
    @staticmethod
    def create(reporter: User, data: NewIncidentData, service: ITService, *,
               suggested_category_id: int | None, now: datetime) -> Incident:
        if not reporter.has_permission(Permission.REPORT_INCIDENT):
            raise UnauthorizedOperationError("This account cannot report incidents")
        if not service.is_active:
            raise InvalidIncidentError(f"Service {service.name} is retired; choose an active service")
        return Incident.report(
            reporter=reporter, title=data.title, description=data.description, service_id=service.id,
            impact=data.impact, urgency=data.urgency, affected_users=data.affected_users,
            suggested_category_id=suggested_category_id, now=now,
        )


class NotificationFactory:
    _TEMPLATES: dict[NotificationType, tuple[str, str]] = {
        NotificationType.INCIDENT_CREATED: ("{number} received", "We logged your incident '{title}'. {detail}"),
        NotificationType.INCIDENT_ASSIGNED: ("{number} assigned to you ({priority})", "'{title}' is now in your queue. {detail}"),
        NotificationType.TECHNICIAN_ASSIGNED: ("{number} has a technician", "{detail}"),
        NotificationType.PRIORITY_CHANGED: ("{number} priority changed", "{detail}"),
        NotificationType.STATUS_CHANGED: ("{number} status update", "{detail}"),
        NotificationType.INFO_REQUESTED: ("{number}: more information needed", "The technician asks: {detail}"),
        NotificationType.INFO_PROVIDED: ("{number}: reporter replied", "{detail}"),
        NotificationType.SLA_WARNING: ("{number} SLA at risk", "{detail}"),
        NotificationType.SLA_VIOLATED: ("{number} SLA VIOLATED", "{detail}"),
        NotificationType.INCIDENT_RESOLVED: ("{number} resolved", "Resolution: {detail}. Please verify or reopen."),
        NotificationType.INCIDENT_REOPENED: ("{number} reopened", "{detail}"),
        NotificationType.INCIDENT_CLOSED: ("{number} closed", "{detail}"),
        NotificationType.ESCALATED: ("ESCALATION {number} ({priority})", "{detail}"),
    }

    @classmethod
    def create(cls, *, recipient: User, channel: ChannelType, type: NotificationType,
               incident: IncidentRef | None, detail: str, now: datetime) -> Notification:
        title_fmt, body_fmt = cls._TEMPLATES[type]
        values = {
            "number": incident.number if incident else "",
            "title": incident.title if incident else "",
            "priority": incident.priority.value if incident and incident.priority else "-",
            "detail": detail,
        }
        return Notification(
            id=None, recipient_id=recipient.id, channel=channel, type=type,
            title=title_fmt.format(**values).strip(), body=body_fmt.format(**values).strip(),
            created_at=now, incident_id=incident.id if incident else None,
        )
