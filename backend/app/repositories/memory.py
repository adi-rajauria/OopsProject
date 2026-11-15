"""In-memory repository implementations (Repository pattern, second implementation).

They behave like an identity map: objects are stored by reference. Used by the
domain/service tests so business rules are verified without any database.
"""

from collections import Counter
from dataclasses import replace
from itertools import count

from app.domain.audit import AuditRecord, AuditTrail
from app.domain.category import Category
from app.domain.enums import ACTIVE_WORK_STATUSES, ChannelType, IncidentStatus, Role, SLATarget
from app.domain.feedback import Feedback
from app.domain.incident import Incident
from app.domain.notification import Notification
from app.domain.repositories import (
    AuditRepository,
    CategoryRepository,
    FeedbackRepository,
    IncidentRepository,
    NotificationRepository,
    ServiceRepository,
    SettingsRepository,
    SLAPolicyRepository,
    SLAViolationRepository,
    UnitOfWork,
    UserRepository,
)
from app.domain.service import ITService
from app.domain.sla import SLAPolicy, SLAViolationRecord
from app.domain.users import User

RESOLVED_STATUSES = (IncidentStatus.RESOLVED, IncidentStatus.VERIFIED, IncidentStatus.CLOSED)


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self._items: dict[int, User] = {}
        self._ids = count(1)

    def get(self, user_id: int) -> User | None:
        return self._items.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._items.values() if u.email == email.strip().lower()), None)

    def add(self, user: User) -> User:
        user.assign_id(next(self._ids))
        self._items[user.id] = user
        return user

    def update(self, user: User) -> None:
        self._items[user.id] = user

    def list(self, role: Role | None = None) -> list[User]:
        return [u for u in self._items.values() if role is None or u.role == role]


class InMemoryIncidentRepository(IncidentRepository):
    def __init__(self) -> None:
        self._items: dict[int, Incident] = {}
        self._ids = count(1)
        self._comment_ids = count(1)

    def get(self, incident_id: int) -> Incident | None:
        return self._items.get(incident_id)

    def add(self, incident: Incident) -> Incident:
        incident.assign_id(next(self._ids))
        self.update(incident)
        return incident

    def update(self, incident: Incident) -> None:
        for comment in incident.comments:
            if comment.id is None:
                comment.id = next(self._comment_ids)
        self._items[incident.id] = incident

    def list_unclosed(self) -> list[Incident]:
        return [i for i in self._items.values() if i.status is not IncidentStatus.CLOSED]

    def list_all(self) -> list[Incident]:
        return list(self._items.values())

    def active_counts_by_technician(self) -> dict[int, int]:
        return dict(Counter(i.assigned_technician_id for i in self._items.values()
                            if i.assigned_technician_id is not None and i.status in ACTIVE_WORK_STATUSES))

    def resolved_counts_for_service(self, service_id: int) -> dict[int, int]:
        return dict(Counter(i.assigned_technician_id for i in self._items.values()
                            if i.service_id == service_id and i.assigned_technician_id is not None
                            and i.status in RESOLVED_STATUSES))


class _InMemoryEntityRepository[T]:
    """Shared storage for simple entities that have assign_id() and a code."""

    def __init__(self) -> None:
        self._items: dict[int, T] = {}
        self._ids = count(1)

    def get(self, entity_id: int) -> T | None:
        return self._items.get(entity_id)

    def get_by_code(self, code: str) -> T | None:
        return next((e for e in self._items.values() if e.code == code.strip().upper()), None)

    def list(self, active_only: bool = False) -> list[T]:
        return [e for e in self._items.values() if not active_only or e.is_active]

    def add(self, entity: T) -> T:
        entity.assign_id(next(self._ids))
        self._items[entity.id] = entity
        return entity

    def update(self, entity: T) -> None:
        self._items[entity.id] = entity


class InMemoryServiceRepository(_InMemoryEntityRepository[ITService], ServiceRepository):
    pass


class InMemoryCategoryRepository(_InMemoryEntityRepository[Category], CategoryRepository):
    pass


class InMemorySLAPolicyRepository(SLAPolicyRepository):
    def __init__(self) -> None:
        self._items: dict[int, SLAPolicy] = {}
        self._ids = count(1)

    def get(self, policy_id: int) -> SLAPolicy | None:
        return self._items.get(policy_id)

    def list(self) -> list[SLAPolicy]:
        return list(self._items.values())

    def add(self, policy: SLAPolicy) -> SLAPolicy:
        policy.assign_id(next(self._ids))
        self._items[policy.id] = policy
        return policy

    def update(self, policy: SLAPolicy) -> None:
        self._items[policy.id] = policy

    def delete(self, policy_id: int) -> None:
        self._items.pop(policy_id, None)


class InMemoryAuditRepository(AuditRepository):
    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
        self._ids = count(1)

    def add(self, record: AuditRecord) -> AuditRecord:
        stored = replace(record, id=next(self._ids))
        self._records.append(stored)
        return stored

    def trail_for(self, incident_id: int) -> AuditTrail:
        return AuditTrail(incident_id, (r for r in self._records if r.incident_id == incident_id))

    def list_recent(self, *, limit: int = 100, offset: int = 0, incident_id: int | None = None,
                    actor_id: int | None = None, action: str | None = None) -> list[AuditRecord]:
        matches = [r for r in reversed(self._records)
                   if (incident_id is None or r.incident_id == incident_id)
                   and (actor_id is None or r.actor_id == actor_id)
                   and (action is None or r.action == action)]
        return matches[offset:offset + limit]


class InMemoryNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        self._items: dict[int, Notification] = {}
        self._ids = count(1)

    def add(self, notification: Notification) -> Notification:
        notification.assign_id(next(self._ids))
        self._items[notification.id] = notification
        return notification

    def get(self, notification_id: int) -> Notification | None:
        return self._items.get(notification_id)

    def update(self, notification: Notification) -> None:
        self._items[notification.id] = notification

    def list_for_user(self, user_id: int, *, channel: ChannelType | None = ChannelType.IN_APP,
                      unread_only: bool = False, limit: int = 50) -> list[Notification]:
        matches = [n for n in reversed(self._items.values())
                   if n.recipient_id == user_id and (channel is None or n.channel == channel)
                   and (not unread_only or not n.is_read)]
        return matches[:limit]

    def list_all(self, *, limit: int = 200) -> list[Notification]:
        return list(reversed(self._items.values()))[:limit]


class InMemorySLAViolationRepository(SLAViolationRepository):
    def __init__(self) -> None:
        self._items: list[SLAViolationRecord] = []
        self._ids = count(1)

    def add(self, violation: SLAViolationRecord) -> SLAViolationRecord:
        stored = replace(violation, id=next(self._ids))
        self._items.append(stored)
        return stored

    def exists(self, incident_id: int, target: SLATarget) -> bool:
        return any(v.incident_id == incident_id and v.target == target for v in self._items)

    def list(self, *, limit: int = 200) -> list[SLAViolationRecord]:
        return list(reversed(self._items))[:limit]


class InMemoryFeedbackRepository(FeedbackRepository):
    def __init__(self) -> None:
        self._items: dict[int, Feedback] = {}
        self._ids = count(1)

    def add(self, feedback: Feedback) -> Feedback:
        stored = replace(feedback, id=next(self._ids))
        self._items[stored.incident_id] = stored
        return stored

    def get_for_incident(self, incident_id: int) -> Feedback | None:
        return self._items.get(incident_id)

    def list(self) -> list[Feedback]:
        return list(self._items.values())


class InMemorySettingsRepository(SettingsRepository):
    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def set(self, key: str, value: str) -> None:
        self._values[key] = value


class InMemoryUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.incidents = InMemoryIncidentRepository()
        self.services = InMemoryServiceRepository()
        self.categories = InMemoryCategoryRepository()
        self.sla_policies = InMemorySLAPolicyRepository()
        self.audit = InMemoryAuditRepository()
        self.notifications = InMemoryNotificationRepository()
        self.sla_violations = InMemorySLAViolationRepository()
        self.feedback = InMemoryFeedbackRepository()
        self.settings = InMemorySettingsRepository()
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        """In-memory objects are not transactional; tests only assert on committed flows."""
