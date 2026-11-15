"""SQLAlchemy implementations of the domain repository interfaces."""

import functools
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.audit import AuditRecord, AuditTrail
from app.domain.category import Category
from app.domain.clock import Clock, SystemClock, ensure_utc
from app.domain.enums import ACTIVE_WORK_STATUSES, ChannelType, IncidentStatus, LinkType, Role, SLATarget
from app.domain.exceptions import PersistenceError
from app.domain.feedback import Feedback
from app.domain.incident import Incident
from app.domain.links import IncidentLink
from app.domain.notification import Notification
from app.domain.repositories import (
    AuditRepository,
    CategoryRepository,
    FeedbackRepository,
    IncidentLinkRepository,
    IncidentRepository,
    NotificationRepository,
    ServiceRepository,
    SettingsRepository,
    SLAPolicyRepository,
    SLAViolationRepository,
    UnitOfWork,
    UserRepository,
)
from app.domain.search import SearchCriteria, SearchPage, SortOrder
from app.domain.service import ITService
from app.domain.sla import SLAPolicy, SLAViolationRecord
from app.domain.users import User
from app.repositories import mappers
from app.repositories.orm import (
    AuditRecordRow,
    CategoryRow,
    FeedbackRow,
    IncidentLinkRow,
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
            raise PersistenceError(
                "The database is unavailable or rejected the operation", details={"reason": type(exc).__name__}
            ) from exc

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

    def list_all(self) -> list[Incident]:
        return [
            mappers.incident_to_domain(r) for r in self._session.scalars(select(IncidentRow).order_by(IncidentRow.id))
        ]

    def search(self, criteria: SearchCriteria) -> SearchPage:
        stmt = self._filtered(criteria)
        total = self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = self._ordered(stmt, criteria.sort).offset(criteria.offset).limit(criteria.page_size)
        items = [mappers.incident_to_domain(r) for r in self._session.scalars(stmt)]
        return SearchPage(items, total, criteria.page, criteria.page_size)

    @staticmethod
    def _filtered(c: SearchCriteria) -> Select:
        """SQL translation of SearchCriteria.matches()."""
        r = IncidentRow
        conditions = []
        if c.incident_id is not None:
            conditions.append(r.id == c.incident_id)
        if c.created_from is not None:
            conditions.append(r.created_at >= c.created_from)
        if c.created_to is not None:
            conditions.append(r.created_at <= c.created_to)
        if c.statuses:
            conditions.append(r.status.in_([s.value for s in c.statuses]))
        if c.priorities:
            conditions.append(r.priority.in_([p.value for p in c.priorities]))
        if c.category_ids:
            conditions.append(r.category_id.in_(c.category_ids))
        if c.service_ids:
            conditions.append(r.service_id.in_(c.service_ids))
        if c.technician_id is not None:
            conditions.append(r.assigned_technician_id == c.technician_id)
        if c.unassigned_only:
            conditions.append(r.assigned_technician_id.is_(None))
        if c.sla_statuses:
            conditions.append(r.sla_status.in_([s.value for s in c.sla_statuses]))
        if c.reporter_id is not None:
            conditions.append(r.reporter_id == c.reporter_id)
        if c.open_only:
            conditions.append(r.status.not_in(RESOLVED_VALUES))
        if c.text_term:
            conditions.append(
                or_(
                    func.lower(r.title).contains(c.text_term, autoescape=True),
                    func.lower(r.description).contains(c.text_term, autoescape=True),
                )
            )
        return select(r).where(*conditions)

    @staticmethod
    def _ordered(stmt: Select, order: SortOrder) -> Select:
        r = IncidentRow
        match order:
            case SortOrder.OLDEST:
                return stmt.order_by(r.created_at, r.id)
            case SortOrder.PRIORITY:
                return stmt.order_by(r.priority.is_(None), r.priority, r.created_at.desc(), r.id.desc())
            case SortOrder.RECENTLY_UPDATED:
                return stmt.order_by(r.updated_at.desc(), r.id.desc())
            case _:
                return stmt.order_by(r.created_at.desc(), r.id.desc())

    def recent_for_service(self, service_id: int, since: datetime) -> list[Incident]:
        stmt = select(IncidentRow).where(
            IncidentRow.service_id == service_id,
            IncidentRow.created_at >= since,
            IncidentRow.status != IncidentStatus.CLOSED.value,
        )
        return [mappers.incident_to_domain(r) for r in self._session.scalars(stmt.order_by(IncidentRow.id))]

    def active_counts_by_technician(self) -> dict[int, int]:
        stmt = (
            select(IncidentRow.assigned_technician_id, func.count())
            .where(IncidentRow.assigned_technician_id.is_not(None), IncidentRow.status.in_(ACTIVE_VALUES))
            .group_by(IncidentRow.assigned_technician_id)
        )
        return {tech_id: n for tech_id, n in self._session.execute(stmt)}

    def resolved_counts_for_service(self, service_id: int) -> dict[int, int]:
        stmt = (
            select(IncidentRow.assigned_technician_id, func.count())
            .where(
                IncidentRow.service_id == service_id,
                IncidentRow.assigned_technician_id.is_not(None),
                IncidentRow.status.in_(RESOLVED_VALUES),
            )
            .group_by(IncidentRow.assigned_technician_id)
        )
        return {tech_id: n for tech_id, n in self._session.execute(stmt)}


class SqlIncidentLinkRepository(_SqlRepository, IncidentLinkRepository):
    def add(self, link: IncidentLink) -> IncidentLink:
        self._session.add(
            IncidentLinkRow(
                incident_id=link.incident_id,
                related_incident_id=link.related_incident_id,
                similarity=link.similarity,
                link_type=link.link_type.value,
                created_at=link.created_at,
            )
        )
        self._session.flush()
        return link

    def list_for(self, incident_id: int) -> list[IncidentLink]:
        stmt = (
            select(IncidentLinkRow)
            .where(or_(IncidentLinkRow.incident_id == incident_id, IncidentLinkRow.related_incident_id == incident_id))
            .order_by(IncidentLinkRow.similarity.desc())
        )
        return [
            IncidentLink(
                incident_id=r.incident_id,
                related_incident_id=r.related_incident_id,
                similarity=r.similarity,
                link_type=LinkType(r.link_type),
                created_at=ensure_utc(r.created_at),
            )
            for r in self._session.scalars(stmt)
        ]


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
        stmt = (
            select(AuditRecordRow)
            .where(AuditRecordRow.incident_id == incident_id)
            .order_by(AuditRecordRow.created_at, AuditRecordRow.id)
        )
        return AuditTrail(incident_id, (mappers.audit_to_domain(r) for r in self._session.scalars(stmt)))

    def list_recent(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        incident_id: int | None = None,
        actor_id: int | None = None,
        action: str | None = None,
    ) -> list[AuditRecord]:
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

    def list_for_user(
        self,
        user_id: int,
        *,
        channel: ChannelType | None = ChannelType.IN_APP,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        stmt = (
            select(NotificationRow)
            .where(NotificationRow.recipient_id == user_id)
            .order_by(NotificationRow.created_at.desc(), NotificationRow.id.desc())
            .limit(limit)
        )
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
        row = SLAViolationRow(
            incident_id=violation.incident_id,
            target=violation.target.value,
            due_at=violation.due_at,
            detected_at=violation.detected_at,
            overdue_minutes=violation.overdue_minutes,
        )
        self._session.add(row)
        self._session.flush()
        return replace(violation, id=row.id)

    def exists(self, incident_id: int, target: SLATarget) -> bool:
        stmt = (
            select(func.count())
            .select_from(SLAViolationRow)
            .where(SLAViolationRow.incident_id == incident_id, SLAViolationRow.target == target.value)
        )
        return bool(self._session.scalar(stmt))

    def list(self, *, limit: int = 200) -> list[SLAViolationRecord]:
        stmt = select(SLAViolationRow).order_by(SLAViolationRow.detected_at.desc()).limit(limit)
        return [mappers.violation_to_domain(r) for r in self._session.scalars(stmt)]


class SqlFeedbackRepository(_SqlRepository, FeedbackRepository):
    def add(self, feedback: Feedback) -> Feedback:
        row = FeedbackRow(
            incident_id=feedback.incident_id,
            employee_id=feedback.employee_id,
            rating=feedback.rating,
            comment=feedback.comment,
            created_at=feedback.created_at,
        )
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
        super().__init__()
        self._session = session
        self.users = SqlUserRepository(session)
        self.incidents = SqlIncidentRepository(session, clock or SystemClock())
        self.links = SqlIncidentLinkRepository(session)
        self.services = SqlServiceRepository(session)
        self.categories = SqlCategoryRepository(session)
        self.sla_policies = SqlSLAPolicyRepository(session)
        self.audit = SqlAuditRepository(session)
        self.notifications = SqlNotificationRepository(session)
        self.sla_violations = SqlSLAViolationRepository(session)
        self.feedback = SqlFeedbackRepository(session)
        self.settings = SqlSettingsRepository(session)

    @translate_db_errors
    def _commit(self) -> None:
        try:
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise

    def _rollback(self) -> None:
        self._session.rollback()
