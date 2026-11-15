"""SQLAlchemy ORM models (persistence model, separate from the domain model).

Only portable column types (String, Integer, Boolean, DateTime, JSON, Float, Text)
so the same models run on PostgreSQL and on SQLite in tests.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

TZDateTime = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    admin_level: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(30))
    department: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime)

    technician_profile: Mapped["TechnicianProfileRow | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False, lazy="joined"
    )


class TechnicianProfileRow(Base):
    __tablename__ = "technician_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience_years: Mapped[int] = mapped_column(Integer, default=0)
    max_workload: Mapped[int] = mapped_column(Integer, default=8)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_team_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    team: Mapped[str] = mapped_column(String(60), default="General")

    user: Mapped[UserRow] = relationship(back_populates="technician_profile")


class ServiceDependencyRow(Base):
    __tablename__ = "service_dependencies"

    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), primary_key=True)
    depends_on_service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), primary_key=True)


class ServiceRow(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    business_criticality: Mapped[int] = mapped_column(Integer)
    owner_team: Mapped[str] = mapped_column(String(60), default="General")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    dependencies: Mapped[list[ServiceDependencyRow]] = relationship(
        foreign_keys=[ServiceDependencyRow.service_id], cascade="all, delete-orphan", lazy="selectin"
    )


class CategoryRow(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SLAPolicyRow(Base):
    __tablename__ = "sla_policies"
    __table_args__ = (UniqueConstraint("priority", "service_id", name="uq_sla_priority_service"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    priority: Mapped[str] = mapped_column(String(2))
    service_id: Mapped[int | None] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    response_minutes: Mapped[int] = mapped_column(Integer)
    resolution_minutes: Mapped[int] = mapped_column(Integer)
    warning_threshold_pct: Mapped[int] = mapped_column(Integer, default=75)


class IncidentRow(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_status_priority", "status", "priority"),
        Index("ix_incidents_service_created", "service_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), index=True)
    suggested_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    impact: Mapped[int] = mapped_column(Integer)
    urgency: Mapped[int] = mapped_column(Integer)
    affected_users: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[str | None] = mapped_column(String(2))
    priority_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))
    assigned_technician_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    # SLA clock (composition: stored inline with its incident)
    sla_policy_id: Mapped[int | None] = mapped_column(ForeignKey("sla_policies.id", ondelete="SET NULL"))
    sla_response_minutes: Mapped[int | None] = mapped_column(Integer)
    sla_resolution_minutes: Mapped[int | None] = mapped_column(Integer)
    sla_warning_pct: Mapped[int | None] = mapped_column(Integer)
    response_due_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    resolution_due_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    response_warned: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_warned: Mapped[bool] = mapped_column(Boolean, default=False)
    response_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    sla_paused_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sla_paused_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    sla_status: Mapped[str | None] = mapped_column(String(10), index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    verified_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(TZDateTime)
    resolution_summary: Mapped[str | None] = mapped_column(Text)
    closure_notes: Mapped[str | None] = mapped_column(Text)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    parent_incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime)

    comments: Mapped[list["CommentRow"]] = relationship(
        cascade="all, delete-orphan", order_by="CommentRow.id", lazy="selectin"
    )


class CommentRow(Base):
    __tablename__ = "incident_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime)


class IncidentLinkRow(Base):
    __tablename__ = "incident_links"

    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True)
    related_incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True)
    similarity: Mapped[float] = mapped_column(Float)
    link_type: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(TZDateTime)


class AuditRecordRow(Base):
    __tablename__ = "audit_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    actor_name: Mapped[str] = mapped_column(String(120), default="SYSTEM")
    action: Mapped[str] = mapped_column(String(40), index=True)
    previous_state: Mapped[str | None] = mapped_column(String(20))
    new_state: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, index=True)


class SLAViolationRow(Base):
    __tablename__ = "sla_violations"
    __table_args__ = (UniqueConstraint("incident_id", "target", name="uq_violation_incident_target"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    target: Mapped[str] = mapped_column(String(12))
    due_at: Mapped[datetime] = mapped_column(TZDateTime)
    detected_at: Mapped[datetime] = mapped_column(TZDateTime)
    overdue_minutes: Mapped[int] = mapped_column(Integer)


class NotificationRow(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_recipient_read", "recipient_id", "is_read"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(10))
    event_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_error: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(TZDateTime, index=True)


class FeedbackRow(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), unique=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(TZDateTime)


class SystemSettingRow(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
