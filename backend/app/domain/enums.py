from enum import StrEnum


class Role(StrEnum):
    EMPLOYEE = "EMPLOYEE"
    TECHNICIAN = "TECHNICIAN"
    ADMINISTRATOR = "ADMINISTRATOR"


class AdminLevel(StrEnum):
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
    IT_MANAGER = "IT_MANAGER"


class Permission(StrEnum):
    REPORT_INCIDENT = "REPORT_INCIDENT"
    VIEW_ALL_INCIDENTS = "VIEW_ALL_INCIDENTS"
    WORK_INCIDENTS = "WORK_INCIDENTS"
    ASSIGN_INCIDENTS = "ASSIGN_INCIDENTS"
    OVERRIDE_CLOSE = "OVERRIDE_CLOSE"
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_CONFIGURATION = "MANAGE_CONFIGURATION"
    VIEW_REPORTS = "VIEW_REPORTS"
    VIEW_AUDIT_LOG = "VIEW_AUDIT_LOG"


class IncidentStatus(StrEnum):
    NEW = "NEW"
    CLASSIFIED = "CLASSIFIED"
    ASSIGNED = "ASSIGNED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_INFO = "PENDING_INFO"
    RESOLVED = "RESOLVED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"

    @property
    def counts_as_workload(self) -> bool:
        return self in ACTIVE_WORK_STATUSES

    @property
    def is_open(self) -> bool:
        return self not in (IncidentStatus.RESOLVED, IncidentStatus.VERIFIED, IncidentStatus.CLOSED)


ACTIVE_WORK_STATUSES: frozenset[IncidentStatus] = frozenset(
    {
        IncidentStatus.ASSIGNED,
        IncidentStatus.ACKNOWLEDGED,
        IncidentStatus.IN_PROGRESS,
        IncidentStatus.PENDING_INFO,
    }
)


class Transition(StrEnum):
    """Every lifecycle action; each one is a method on IncidentState."""

    CLASSIFY = "classify"
    ASSIGN = "assign"
    ACKNOWLEDGE = "acknowledge"
    START_WORK = "start_work"
    REQUEST_INFO = "request_info"
    PROVIDE_INFO = "provide_info"
    RESOLVE = "resolve"
    REOPEN = "reopen"
    VERIFY = "verify"
    CLOSE = "close"


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"

    @property
    def label(self) -> str:
        return {"P1": "Critical", "P2": "High", "P3": "Medium", "P4": "Low"}[self.value]

    @property
    def rank(self) -> int:
        return int(self.value[1])


class SLAStatus(StrEnum):
    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"
    MET = "MET"


class SLATarget(StrEnum):
    RESPONSE = "RESPONSE"
    RESOLUTION = "RESOLUTION"


class CommentKind(StrEnum):
    COMMENT = "COMMENT"
    NOTE = "NOTE"
    INFO_REQUEST = "INFO_REQUEST"
    INFO_REPLY = "INFO_REPLY"
    RESOLUTION = "RESOLUTION"


class ChannelType(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"


class NotificationType(StrEnum):
    INCIDENT_CREATED = "INCIDENT_CREATED"
    INCIDENT_ASSIGNED = "INCIDENT_ASSIGNED"
    TECHNICIAN_ASSIGNED = "TECHNICIAN_ASSIGNED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    INFO_REQUESTED = "INFO_REQUESTED"
    INFO_PROVIDED = "INFO_PROVIDED"
    SLA_WARNING = "SLA_WARNING"
    SLA_VIOLATED = "SLA_VIOLATED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    INCIDENT_REOPENED = "INCIDENT_REOPENED"
    INCIDENT_CLOSED = "INCIDENT_CLOSED"
    ESCALATED = "ESCALATED"


class LinkType(StrEnum):
    DUPLICATE = "DUPLICATE"
    RELATED = "RELATED"
