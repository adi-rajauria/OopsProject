"""Repository interfaces (Repository pattern) + Unit of Work.

The domain and services depend only on these abstractions. There are two
implementations: SQLAlchemy (PostgreSQL in production, SQLite in API tests) and
in-memory (fast unit/service tests with no database at all).
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from types import TracebackType
from typing import Self

from app.domain.audit import AuditRecord, AuditTrail
from app.domain.category import Category
from app.domain.enums import ChannelType, Role, SLATarget
from app.domain.feedback import Feedback
from app.domain.incident import Incident
from app.domain.links import IncidentLink
from app.domain.notification import Notification
from app.domain.search import SearchCriteria, SearchPage
from app.domain.service import ITService
from app.domain.sla import SLAPolicy, SLAViolationRecord
from app.domain.users import Administrator, Technician, User


class UserRepository(ABC):
    @abstractmethod
    def get(self, user_id: int) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def add(self, user: User) -> User: ...

    @abstractmethod
    def update(self, user: User) -> None: ...

    @abstractmethod
    def list(self, role: Role | None = None) -> list[User]: ...

    def list_technicians(self) -> list[Technician]:
        return [u for u in self.list(Role.TECHNICIAN) if isinstance(u, Technician)]

    def list_administrators(self) -> list[Administrator]:
        return [u for u in self.list(Role.ADMINISTRATOR) if isinstance(u, Administrator)]


class IncidentRepository(ABC):
    @abstractmethod
    def get(self, incident_id: int) -> Incident | None: ...

    @abstractmethod
    def add(self, incident: Incident) -> Incident: ...

    @abstractmethod
    def update(self, incident: Incident) -> None: ...

    @abstractmethod
    def list_unclosed(self) -> list[Incident]: ...

    @abstractmethod
    def list_all(self) -> list[Incident]:
        """Every incident (reports/analytics at demo scale; see scalability notes)."""

    @abstractmethod
    def search(self, criteria: SearchCriteria) -> SearchPage: ...

    @abstractmethod
    def recent_for_service(self, service_id: int, since: datetime) -> list[Incident]:
        """Not-closed incidents on a service created at or after `since` (duplicate candidates)."""

    @abstractmethod
    def active_counts_by_technician(self) -> dict[int, int]:
        """technician id -> number of incidents in ACTIVE_WORK_STATUSES."""

    @abstractmethod
    def resolved_counts_for_service(self, service_id: int) -> dict[int, int]:
        """technician id -> incidents they resolved on this service (experience signal)."""


class IncidentLinkRepository(ABC):
    @abstractmethod
    def add(self, link: IncidentLink) -> IncidentLink: ...

    @abstractmethod
    def list_for(self, incident_id: int) -> list[IncidentLink]:
        """Links in either direction, strongest first."""


class ServiceRepository(ABC):
    @abstractmethod
    def get(self, service_id: int) -> ITService | None: ...

    @abstractmethod
    def get_by_code(self, code: str) -> ITService | None: ...

    @abstractmethod
    def list(self, active_only: bool = False) -> list[ITService]: ...

    @abstractmethod
    def add(self, service: ITService) -> ITService: ...

    @abstractmethod
    def update(self, service: ITService) -> None: ...


class CategoryRepository(ABC):
    @abstractmethod
    def get(self, category_id: int) -> Category | None: ...

    @abstractmethod
    def get_by_code(self, code: str) -> Category | None: ...

    @abstractmethod
    def list(self, active_only: bool = False) -> list[Category]: ...

    @abstractmethod
    def add(self, category: Category) -> Category: ...

    @abstractmethod
    def update(self, category: Category) -> None: ...


class SLAPolicyRepository(ABC):
    @abstractmethod
    def get(self, policy_id: int) -> SLAPolicy | None: ...

    @abstractmethod
    def list(self) -> list[SLAPolicy]: ...

    @abstractmethod
    def add(self, policy: SLAPolicy) -> SLAPolicy: ...

    @abstractmethod
    def update(self, policy: SLAPolicy) -> None: ...

    @abstractmethod
    def delete(self, policy_id: int) -> None: ...


class AuditRepository(ABC):
    @abstractmethod
    def add(self, record: AuditRecord) -> AuditRecord: ...

    @abstractmethod
    def trail_for(self, incident_id: int) -> AuditTrail: ...

    @abstractmethod
    def list_recent(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        incident_id: int | None = None,
        actor_id: int | None = None,
        action: str | None = None,
    ) -> list[AuditRecord]: ...


class NotificationRepository(ABC):
    @abstractmethod
    def add(self, notification: Notification) -> Notification: ...

    @abstractmethod
    def get(self, notification_id: int) -> Notification | None: ...

    @abstractmethod
    def update(self, notification: Notification) -> None: ...

    @abstractmethod
    def list_for_user(
        self,
        user_id: int,
        *,
        channel: ChannelType | None = ChannelType.IN_APP,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]: ...

    @abstractmethod
    def list_all(self, *, limit: int = 200) -> list[Notification]: ...


class SLAViolationRepository(ABC):
    @abstractmethod
    def add(self, violation: SLAViolationRecord) -> SLAViolationRecord: ...

    @abstractmethod
    def exists(self, incident_id: int, target: SLATarget) -> bool: ...

    @abstractmethod
    def list(self, *, limit: int = 200) -> list[SLAViolationRecord]: ...


class FeedbackRepository(ABC):
    @abstractmethod
    def add(self, feedback: Feedback) -> Feedback: ...

    @abstractmethod
    def get_for_incident(self, incident_id: int) -> Feedback | None: ...

    @abstractmethod
    def list(self) -> list[Feedback]: ...


class SettingsRepository(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str) -> None: ...


class UnitOfWork(ABC):
    """Groups the repositories that take part in one business transaction.

    commit() is a template method: the subclass persists (_commit), then the
    callbacks registered with after_commit() run - e.g. real-time pushes, which
    must never announce a change that was rolled back.
    """

    users: UserRepository
    incidents: IncidentRepository
    links: IncidentLinkRepository
    services: ServiceRepository
    categories: CategoryRepository
    sla_policies: SLAPolicyRepository
    audit: AuditRepository
    notifications: NotificationRepository
    sla_violations: SLAViolationRepository
    feedback: FeedbackRepository
    settings: SettingsRepository

    def __init__(self) -> None:
        self._after_commit: list[Callable[[], None]] = []

    def after_commit(self, callback: Callable[[], None]) -> None:
        self._after_commit.append(callback)

    def commit(self) -> None:
        self._commit()
        callbacks, self._after_commit = self._after_commit, []
        for callback in callbacks:
            callback()

    def rollback(self) -> None:
        self._after_commit.clear()
        self._rollback()

    @abstractmethod
    def _commit(self) -> None: ...

    @abstractmethod
    def _rollback(self) -> None: ...

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        if exc_type is not None:
            self.rollback()
