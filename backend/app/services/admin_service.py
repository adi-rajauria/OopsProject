"""Administration: users, technicians, IT services, categories, SLA policies.

Every change is published as an AdministrativeChange event, so the AuditLogger
observer records it without this service knowing about auditing.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.category import Category
from app.domain.clock import Clock
from app.domain.enums import AdminLevel, Permission, Priority, Role
from app.domain.events import AdministrativeChange, EventBus
from app.domain.exceptions import (
    CategoryNotFoundError,
    ConflictError,
    InvalidInputError,
    ServiceNotFoundError,
    SLAPolicyNotFoundError,
    UnauthorizedOperationError,
    UserNotFoundError,
)
from app.domain.repositories import UnitOfWork
from app.domain.service import ITService
from app.domain.sla import SLAPolicy
from app.domain.users import Administrator, Technician, TechnicianProfile, User
from app.services.auth_service import AuthService


@dataclass(frozen=True)
class NewUserData:
    role: Role
    email: str
    full_name: str
    password: str
    phone: str | None = None
    department: str | None = None
    admin_level: AdminLevel | None = None
    profile: TechnicianProfile | None = None


class AdminService:
    def __init__(self, uow: UnitOfWork, clock: Clock, bus: EventBus, auth: AuthService) -> None:
        self._uow = uow
        self._clock = clock
        self._bus = bus
        self._auth = auth

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _require(actor: User, permission: Permission) -> None:
        if not actor.has_permission(permission):
            raise UnauthorizedOperationError(f"Your role ({actor.role.value}) cannot perform this action")

    def _record(self, actor: User, change: str, summary: str) -> None:
        self._bus.publish(
            AdministrativeChange(occurred_at=self._clock.now(), actor_id=actor.id, change=change, summary=summary)
        )
        self._uow.commit()

    def _validate_skills(self, skills: Iterable[str]) -> frozenset[str]:
        known = {c.code for c in self._uow.categories.list()}
        cleaned = frozenset(s.strip().upper() for s in skills if s.strip())
        unknown = cleaned - known
        if unknown:
            raise InvalidInputError(
                f"Unknown skill/category code(s): {', '.join(sorted(unknown))}", details={"field": "skills"}
            )
        return cleaned

    # ------------------------------------------------------------------ users
    def list_users(self, actor: User, role: Role | None = None) -> list[User]:
        self._require(actor, Permission.MANAGE_USERS)
        return self._uow.users.list(role)

    def get_user(self, actor: User, user_id: int) -> User:
        self._require(actor, Permission.MANAGE_USERS)
        user = self._uow.users.get(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    def create_user(self, actor: User, data: NewUserData) -> User:
        self._require(actor, Permission.MANAGE_USERS)
        extra = {}
        if data.role is Role.TECHNICIAN:
            profile = data.profile or TechnicianProfile()
            extra["profile"] = TechnicianProfile(
                skills=self._validate_skills(profile.skills),
                experience_years=profile.experience_years,
                max_workload=profile.max_workload,
                is_available=profile.is_available,
                is_team_lead=profile.is_team_lead,
                team=profile.team,
            )
        if data.role is Role.ADMINISTRATOR:
            extra["admin_level"] = data.admin_level or AdminLevel.SYSTEM_ADMIN
        return self._auth.create_account(
            data.role,
            email=data.email,
            full_name=data.full_name,
            password=data.password,
            actor_id=actor.id,
            phone=data.phone,
            department=data.department,
            **extra,
        )

    def update_user(
        self,
        actor: User,
        user_id: int,
        *,
        full_name: str | None = None,
        phone: str | None = None,
        department: str | None = None,
        admin_level: AdminLevel | None = None,
    ) -> User:
        user = self.get_user(actor, user_id)
        user.update_profile(full_name=full_name, phone=phone, department=department)
        if admin_level is not None:
            if not isinstance(user, Administrator):
                raise InvalidInputError("admin_level applies to administrators only")
            user.set_admin_level(admin_level)
        self._uow.users.update(user)
        self._record(actor, "USER_UPDATED", f"User {user.email} updated")
        return user

    def set_user_active(self, actor: User, user_id: int, active: bool) -> User:
        user = self.get_user(actor, user_id)
        if user.id == actor.id and not active:
            raise InvalidInputError("You cannot deactivate your own account")
        if active:
            user.activate()
        else:
            user.deactivate()
        self._uow.users.update(user)
        self._record(
            actor,
            "USER_ACTIVATED" if active else "USER_DEACTIVATED",
            f"User {user.email} {'activated' if active else 'deactivated'}",
        )
        return user

    def update_technician(self, actor: User, technician_id: int, **changes) -> Technician:
        technician = self.get_user(actor, technician_id)
        if not isinstance(technician, Technician):
            raise InvalidInputError("User is not a technician")
        changes = {k: v for k, v in changes.items() if v is not None}
        if "skills" in changes:
            changes["skills"] = self._validate_skills(changes["skills"])
        technician.update_technician_profile(**changes)
        self._uow.users.update(technician)
        self._record(
            actor,
            "TECHNICIAN_UPDATED",
            f"Technician {technician.email} profile updated: {', '.join(sorted(changes)) or 'no changes'}",
        )
        return technician

    def set_own_availability(self, technician: User, available: bool) -> Technician:
        if not isinstance(technician, Technician):
            raise UnauthorizedOperationError("Only technicians have an availability status")
        technician.set_availability(available)
        self._uow.users.update(technician)
        self._record(
            technician,
            "AVAILABILITY_CHANGED",
            f"{technician.full_name} is now {'available' if available else 'unavailable'}",
        )
        return technician

    # ------------------------------------------------------------------ services
    def list_services(self, active_only: bool = False) -> list[ITService]:
        return self._uow.services.list(active_only)

    def _service(self, service_id: int) -> ITService:
        service = self._uow.services.get(service_id)
        if service is None:
            raise ServiceNotFoundError(service_id)
        return service

    def create_service(
        self,
        actor: User,
        *,
        code: str,
        name: str,
        business_criticality: int,
        owner_team: str = "General",
        description: str = "",
    ) -> ITService:
        self._require(actor, Permission.MANAGE_CONFIGURATION)
        service = ITService(
            id=None,
            code=code,
            name=name,
            business_criticality=business_criticality,
            owner_team=owner_team,
            description=description,
        )
        if self._uow.services.get_by_code(service.code):
            raise ConflictError(f"Service code {service.code} already exists")
        self._uow.services.add(service)
        self._record(
            actor,
            "SERVICE_CREATED",
            f"Service {service.code} ({service.name}) created, criticality {service.business_criticality}",
        )
        return service

    def update_service(self, actor: User, service_id: int, **changes) -> ITService:
        self._require(actor, Permission.MANAGE_CONFIGURATION)
        service = self._service(service_id)
        service.update(**changes)
        self._uow.services.update(service)
        self._record(actor, "SERVICE_UPDATED", f"Service {service.code} updated")
        return service

    def set_dependencies(self, actor: User, service_id: int, depends_on: set[int]) -> ITService:
        self._require(actor, Permission.MANAGE_CONFIGURATION)
        service = self._service(service_id)
        for dep in depends_on:
            self._service(dep)
        self._reject_cycles(service_id, depends_on)
        service.set_dependencies(depends_on)
        self._uow.services.update(service)
        self._record(
            actor,
            "SERVICE_DEPENDENCIES_CHANGED",
            f"Service {service.code} now depends on {sorted(depends_on) or 'nothing'}",
        )
        return service

    def _reject_cycles(self, service_id: int, depends_on: set[int]) -> None:
        """Depth-first search over the dependency graph; a path back to service_id is a cycle."""
        graph = {s.id: set(s.depends_on) for s in self._uow.services.list()}
        graph[service_id] = set(depends_on)
        stack, seen = list(depends_on), set()
        while stack:
            current = stack.pop()
            if current == service_id:
                raise InvalidInputError("This dependency would create a cycle")
            if current not in seen:
                seen.add(current)
                stack.extend(graph.get(current, ()))

    # ------------------------------------------------------------------ categories
    def list_categories(self, active_only: bool = False) -> list[Category]:
        return self._uow.categories.list(active_only)

    def create_category(self, actor: User, *, code: str, name: str, keywords: list[str]) -> Category:
        self._require(actor, Permission.MANAGE_CONFIGURATION)
        category = Category(id=None, code=code, name=name, keywords=keywords)
        if self._uow.categories.get_by_code(category.code):
            raise ConflictError(f"Category code {category.code} already exists")
        self._uow.categories.add(category)
        self._record(
            actor,
            "CATEGORY_CREATED",
            f"Category {category.code} created with keywords {', '.join(category.keywords) or '-'}",
        )
        return category

    def update_category(self, actor: User, category_id: int, **changes) -> Category:
        self._require(actor, Permission.MANAGE_CONFIGURATION)
        category = self._uow.categories.get(category_id)
        if category is None:
            raise CategoryNotFoundError(category_id)
        category.update(**changes)
        self._uow.categories.update(category)
        self._record(actor, "CATEGORY_UPDATED", f"Category {category.code} updated")
        return category

    # ------------------------------------------------------------------ SLA policies
    def list_policies(self, actor: User) -> list[SLAPolicy]:
        self._require(actor, Permission.MANAGE_CONFIGURATION)
        return self._uow.sla_policies.list()

    def create_policy(
        self,
        actor: User,
        *,
        priority: Priority,
        service_id: int | None,
        response_minutes: int,
        resolution_minutes: int,
        warning_threshold_pct: int = 75,
    ) -> SLAPolicy:
        self._require(actor, Permission.MANAGE_CONFIGURATION)
        if service_id is not None:
            self._service(service_id)
        if any(p.priority == priority and p.service_id == service_id for p in self._uow.sla_policies.list()):
            raise ConflictError(f"An SLA policy for {priority.value} / service {service_id} already exists")
        policy = SLAPolicy(
            id=None,
            priority=priority,
            service_id=service_id,
            response_minutes=response_minutes,
            resolution_minutes=resolution_minutes,
            warning_threshold_pct=warning_threshold_pct,
        )
        self._uow.sla_policies.add(policy)
        self._record(
            actor,
            "SLA_POLICY_CREATED",
            f"SLA {priority.value} for "
            f"{'all services' if service_id is None else f'service {service_id}'}: "
            f"{response_minutes} / {resolution_minutes} min",
        )
        return policy

    def update_policy(
        self, actor: User, policy_id: int, *, response_minutes: int, resolution_minutes: int, warning_threshold_pct: int
    ) -> SLAPolicy:
        self._require(actor, Permission.MANAGE_CONFIGURATION)
        policy = self._policy(policy_id)
        policy.update_targets(
            response_minutes=response_minutes,
            resolution_minutes=resolution_minutes,
            warning_threshold_pct=warning_threshold_pct,
        )
        self._uow.sla_policies.update(policy)
        self._record(
            actor,
            "SLA_POLICY_UPDATED",
            f"SLA policy {policy_id} ({policy.priority.value}) now "
            f"{response_minutes} / {resolution_minutes} min, warn at "
            f"{warning_threshold_pct}%",
        )
        return policy

    def delete_policy(self, actor: User, policy_id: int) -> None:
        self._require(actor, Permission.MANAGE_CONFIGURATION)
        policy = self._policy(policy_id)
        if policy.is_default:
            raise InvalidInputError("Default policies cannot be deleted (every priority needs one); edit it instead")
        self._uow.sla_policies.delete(policy_id)
        self._record(
            actor,
            "SLA_POLICY_DELETED",
            f"SLA policy {policy_id} ({policy.priority.value}, service {policy.service_id}) deleted",
        )

    def _policy(self, policy_id: int) -> SLAPolicy:
        policy = self._uow.sla_policies.get(policy_id)
        if policy is None:
            raise SLAPolicyNotFoundError(policy_id)
        return policy
