"""SQLAlchemy implementations of the domain repository interfaces."""

import functools
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.audit import AuditRecord, AuditTrail
from app.domain.category import Category
from app.domain.clock import Clock, SystemClock
from app.domain.enums import ACTIVE_WORK_STATUSES, ChannelType, IncidentStatus, Role, SLATarget
from app.domain.exceptions import PersistenceError
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
from app.repositories import mappers
from app.repositories.orm import (
    AuditRecordRow,
    CategoryRow,
    FeedbackRow,
    IncidentRow,
    NotificationRow,
    ServiceRow,
    SLAPolicyRow,
    SLAViolationRow,
    SystemSettingRow,
    UserRow,
)

RESOLVED_VALUES = (IncidentStatus.RESOLVED.value, IncidentStatus.VERIFIED.value, IncidentStatus.CLOSED.value)
ACTIVE_VALUES = tuple(s.value for s in ACTIVE_WORK_STATUSES)


def translate_db_errors[**P, R](method: Callable[P, R]) -> Callable[P, R]:
    """Convert any SQLAlchemy failure into the domain's PersistenceError (spec: database failure)."""

    @functools.wraps(method)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return method(*args, **kwargs)
        except SQLAlchemyError as exc:
            raise PersistenceError("The database is unavailable or rejected the operation",
                                   details={"reason": type(exc).__name__}) from exc

    return wrapper


class _SqlRepository:
    """Every public method of a subclass is automatically wrapped by translate_db_errors."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for name, attr in list(vars(cls).items()):
            if callable(attr) and not name.startswith("_"):
                setattr(cls, name, translate_db_errors(attr))

    def _row[T](self, model: type[T], key: Any) -> T:
        row = self._session.get(model, key)
        if row is None:
            raise PersistenceError(f"{model.__name__} {key} vanished during update")
        return row


class SqlUserRepository(_SqlRepository, UserRepository):
    def get(self, user_id: int) -> User | None:
        row = self._session.get(UserRow, user_id)
        return mappers.user_to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        row = self._session.scalar(select(UserRow).where(UserRow.email == email.strip().lower()))
        return mappers.user_to_domain(row) if row else None

    def add(self, user: User) -> User:
        row = mappers.user_to_row(user, UserRow())
        self._session.add(row)
        self._session.flush()
        user.assign_id(row.id)
        return user

    def update(self, user: User) -> None:
        mappers.user_to_row(user, self._row(UserRow, user.id))
        self._session.flush()

    def list(self, role: Role | None = None) -> list[User]:
        stmt = select(UserRow).order_by(UserRow.id)
        if role is not None:
            stmt = stmt.where(UserRow.role == role.value)
        return [mappers.user_to_domain(r) for r in self._session.scalars(stmt).unique()]


class SqlIncidentRepository(_SqlRepository, IncidentRepository):
    def __init__(self, session: Session, clock: Clock) -> None:
        super().__init__(session)
        self._clock = clock

    def get(self, incident_id: int) -> Incident | None:
        row = self._session.get(IncidentRow, incident_id)
        return mappers.incident_to_domain(row) if row else None

    def add(self, incident: Incident) -> Incident:
        row = IncidentRow()
        new_comments = mappers.incident_to_row(incident, row, self._clock.now())
        self._session.add(row)
        self._session.flush()
        incident.assign_id(row.id)
        self._copy_comment_ids(new_comments)
        return incident

    def update(self, incident: Incident) -> None:
        row = self._row(IncidentRow, incident.id)
        new_comments = mappers.incident_to_row(incident, row, self._clock.now())
        self._session.flush()
        self._copy_comment_ids(new_comments)

    @staticmethod
    def _copy_comment_ids(pairs) -> None:
        for comment, comment_row in pairs:
            comment.id = comment_row.id

    def list_unclosed(self) -> list[Incident]:
        stmt = select(IncidentRow).where(IncidentRow.status != IncidentStatus.CLOSED.value).order_by(IncidentRow.id)
        return [mappers.incident_to_domain(r) for r in self._session.scalars(stmt)]

    def active_counts_by_technician(self) -> dict[int, int]:
        stmt = (select(IncidentRow.assigned_technician_id, func.count())
                .where(IncidentRow.assigned_technician_id.is_not(None), IncidentRow.status.in_(ACTIVE_VALUES))
                .group_by(IncidentRow.assigned_technician_id))
        return {tech_id: n for tech_id, n in self._session.execute(stmt)}

    def resolved_counts_for_service(self, service_id: int) -> dict[int, int]:
        stmt = (select(IncidentRow.assigned_technician_id, func.count())
                .where(IncidentRow.service_id == service_id, IncidentRow.assigned_technician_id.is_not(None),
                       IncidentRow.status.in_(RESOLVED_VALUES))
                .group_by(IncidentRow.assigned_technician_id))
        return {tech_id: n for tech_id, n in self._session.execute(stmt)}


class SqlServiceRepository(_SqlRepository, ServiceRepository):
    def get(self, service_id: int) -> ITService | None:
        row = self._session.get(ServiceRow, service_id)
        return mappers.service_to_domain(row) if row else None

    def get_by_code(self, code: str) -> ITService | None:
        row = self._session.scalar(select(ServiceRow).where(ServiceRow.code == code.strip().upper()))
        return mappers.service_to_domain(row) if row else None

    def list(self, active_only: bool = False) -> list[ITService]:
        stmt = select(ServiceRow).order_by(ServiceRow.name)
        if active_only:
            stmt = stmt.where(ServiceRow.is_active.is_(True))
        return [mappers.service_to_domain(r) for r in self._session.scalars(stmt)]

    def add(self, service: ITService) -> ITService:
        row = mappers.service_to_row(service, ServiceRow(dependencies=[]))
        self._session.add(row)
        self._session.flush()
        service.assign_id(row.id)
        return service

    def update(self, service: ITService) -> None:
        mappers.service_to_row(service, self._row(ServiceRow, service.id))
        self._session.flush()


class SqlCategoryRepository(_SqlRepository, CategoryRepository):
    def get(self, category_id: int) -> Category | None:
        row = self._session.get(CategoryRow, category_id)
        return mappers.category_to_domain(row) if row else None

    def get_by_code(self, code: str) -> Category | None:
        row = self._session.scalar(select(CategoryRow).where(CategoryRow.code == code.strip().upper()))
        return mappers.category_to_domain(row) if row else None

    def list(self, active_only: bool = False) -> list[Category]:
        stmt = select(CategoryRow).order_by(CategoryRow.name)
        if active_only:
            stmt = stmt.where(CategoryRow.is_active.is_(True))
        return [mappers.category_to_domain(r) for r in self._session.scalars(stmt)]

    def add(self, category: Category) -> Category:
        row = mappers.category_to_row(category, CategoryRow())
        self._session.add(row)
        self._session.flush()
        category.assign_id(row.id)
        return category

    def update(self, category: Category) -> None:
        mappers.category_to_row(category, self._row(CategoryRow, category.id))
        self._session.flush()


class SqlSLAPolicyRepository(_SqlRepository, SLAPolicyRepository):
    def get(self, policy_id: int) -> SLAPolicy | None:
        row = self._session.get(SLAPolicyRow, policy_id)
        return mappers.policy_to_domain(row) if row else None

    def list(self) -> list[SLAPolicy]:
        stmt = select(SLAPolicyRow).order_by(SLAPolicyRow.priority, SLAPolicyRow.service_id)
        return [mappers.policy_to_domain(r) for r in self._session.scalars(stmt)]

    def add(self, policy: SLAPolicy) -> SLAPolicy:
        row = mappers.policy_to_row(policy, SLAPolicyRow())
        self._session.add(row)
        self._session.flush()
        policy.assign_id(row.id)
        return policy

    def update(self, policy: SLAPolicy) -> None:
        mappers.policy_to_row(policy, self._row(SLAPolicyRow, policy.id))
        self._session.flush()

    def delete(self, policy_id: int) -> None:
        row = self._session.get(SLAPolicyRow, policy_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()


class SqlAuditRepository(_SqlRepository, AuditRepository):
    def add(self, record: AuditRecord) -> AuditRecord:
        row = mappers.audit_to_row(record)
        self._session.add(row)
        self._session.flush()
        return replace(record, id=row.id)

    def trail_for(self, incident_id: int) -> AuditTrail:
        stmt = (select(AuditRecordRow).where(AuditRecordRow.incident_id == incident_id)
                .order_by(AuditRecordRow.created_at, AuditRecordRow.id))
        return AuditTrail(incident_id, (mappers.audit_to_domain(r) for r in self._session.scalars(stmt)))

    def list_recent(self, *, limit: int = 100, offset: int = 0, incident_id: int | None = None,
                    actor_id: int | None = None, action: str | None = None) -> list[AuditRecord]:
        stmt = select(AuditRecordRow).order_by(AuditRecordRow.created_at.desc(), AuditRecordRow.id.desc())
        if incident_id is not None:
            stmt = stmt.where(AuditRecordRow.incident_id == incident_id)
        if actor_id is not None:
            stmt = stmt.where(AuditRecordRow.actor_id == actor_id)
        if action is not None:
            stmt = stmt.where(AuditRecordRow.action == action)
        return [mappers.audit_to_domain(r) for r in self._session.scalars(stmt.offset(offset).limit(limit))]


class SqlNotificationRepository(_SqlRepository, NotificationRepository):
    def add(self, notification: Notification) -> Notification:
        row = mappers.notification_to_row(notification, NotificationRow())
        self._session.add(row)
        self._session.flush()
        notification.assign_id(row.id)
        return notification

    def get(self, notification_id: int) -> Notification | None:
        row = self._session.get(NotificationRow, notification_id)
        return mappers.notification_to_domain(row) if row else None

    def update(self, notification: Notification) -> None:
        mappers.notification_to_row(notification, self._row(NotificationRow, notification.id))
        self._session.flush()

    def list_for_user(self, user_id: int, *, channel: ChannelType | None = ChannelType.IN_APP,
                      unread_only: bool = False, limit: int = 50) -> list[Notification]:
        stmt = (select(NotificationRow).where(NotificationRow.recipient_id == user_id)
                .order_by(NotificationRow.created_at.desc(), NotificationRow.id.desc()).limit(limit))
        if channel is not None:
            stmt = stmt.where(NotificationRow.channel == channel.value)
        if unread_only:
            stmt = stmt.where(NotificationRow.is_read.is_(False))
        return [mappers.notification_to_domain(r) for r in self._session.scalars(stmt)]

    def list_all(self, *, limit: int = 200) -> list[Notification]:
        stmt = select(NotificationRow).order_by(NotificationRow.id.desc()).limit(limit)
        return [mappers.notification_to_domain(r) for r in self._session.scalars(stmt)]


class SqlSLAViolationRepository(_SqlRepository, SLAViolationRepository):
    def add(self, violation: SLAViolationRecord) -> SLAViolationRecord:
        row = SLAViolationRow(incident_id=violation.incident_id, target=violation.target.value,
                              due_at=violation.due_at, detected_at=violation.detected_at,
                              overdue_minutes=violation.overdue_minutes)
        self._session.add(row)
        self._session.flush()
        return replace(violation, id=row.id)

    def exists(self, incident_id: int, target: SLATarget) -> bool:
        stmt = select(func.count()).select_from(SLAViolationRow).where(
            SLAViolationRow.incident_id == incident_id, SLAViolationRow.target == target.value)
        return bool(self._session.scalar(stmt))

    def list(self, *, limit: int = 200) -> list[SLAViolationRecord]:
        stmt = select(SLAViolationRow).order_by(SLAViolationRow.detected_at.desc()).limit(limit)
        return [mappers.violation_to_domain(r) for r in self._session.scalars(stmt)]


class SqlFeedbackRepository(_SqlRepository, FeedbackRepository):
    def add(self, feedback: Feedback) -> Feedback:
        row = FeedbackRow(incident_id=feedback.incident_id, employee_id=feedback.employee_id,
                          rating=feedback.rating, comment=feedback.comment, created_at=feedback.created_at)
        self._session.add(row)
        self._session.flush()
        return replace(feedback, id=row.id)

    def get_for_incident(self, incident_id: int) -> Feedback | None:
        row = self._session.scalar(select(FeedbackRow).where(FeedbackRow.incident_id == incident_id))
        return mappers.feedback_to_domain(row) if row else None

    def list(self) -> list[Feedback]:
        return [mappers.feedback_to_domain(r) for r in self._session.scalars(select(FeedbackRow))]


class SqlSettingsRepository(_SqlRepository, SettingsRepository):
    def get(self, key: str) -> str | None:
        row = self._session.get(SystemSettingRow, key)
        return row.value if row else None

    def set(self, key: str, value: str) -> None:
        row = self._session.get(SystemSettingRow, key)
        if row is None:
            self._session.add(SystemSettingRow(key=key, value=value))
        else:
            row.value = value
        self._session.flush()


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: Session, clock: Clock | None = None) -> None:
        self._session = session
        self.users = SqlUserRepository(session)
        self.incidents = SqlIncidentRepository(session, clock or SystemClock())
        self.services = SqlServiceRepository(session)
        self.categories = SqlCategoryRepository(session)
        self.sla_policies = SqlSLAPolicyRepository(session)
        self.audit = SqlAuditRepository(session)
        self.notifications = SqlNotificationRepository(session)
        self.sla_violations = SqlSLAViolationRepository(session)
        self.feedback = SqlFeedbackRepository(session)
        self.settings = SqlSettingsRepository(session)

    @translate_db_errors
    def commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise

    def rollback(self) -> None:
        self._session.rollback()
