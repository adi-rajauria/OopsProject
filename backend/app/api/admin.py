from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api import presenters
from app.api.schemas import (
    AuditRecordOut,
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    DependenciesIn,
    EscalationSettings,
    NotificationOut,
    PolicyIn,
    PolicyOut,
    PolicyUpdate,
    ServiceIn,
    ServiceOut,
    ServiceUpdate,
    StrategyIn,
    TechnicianProfileUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.core.deps import Container, require
from app.domain.enums import Permission, Role
from app.domain.users import TechnicianProfile, User
from app.services.admin_service import NewUserData
from app.services.assignment_service import StrategyInfo
from app.services.sla_service import SLACheckSummary

router = APIRouter(prefix="/api/admin", tags=["admin"])
# Role guard applied to every endpoint in this router via the Admin dependency.
Admin = Annotated[User, Depends(require(Permission.MANAGE_CONFIGURATION, Permission.MANAGE_USERS))]


# --- users & technicians ---------------------------------------------------------------------


@router.get("/users", response_model=list[UserOut])
def list_users(admin: Admin, container: Container, role: Role | None = None) -> list[UserOut]:
    return [UserOut.from_domain(u) for u in container.admin.list_users(admin, role)]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, admin: Admin, container: Container) -> UserOut:
    profile = TechnicianProfile(**body.technician.model_dump()) if body.technician else None
    data = NewUserData(
        role=body.role,
        email=body.email,
        full_name=body.full_name,
        password=body.password,
        phone=body.phone,
        department=body.department,
        admin_level=body.admin_level,
        profile=profile,
    )
    return UserOut.from_domain(container.admin.create_user(admin, data))


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, admin: Admin, container: Container) -> UserOut:
    return UserOut.from_domain(container.admin.update_user(admin, user_id, **body.model_dump(exclude_none=True)))


@router.post("/users/{user_id}/activate", response_model=UserOut)
def activate_user(user_id: int, admin: Admin, container: Container) -> UserOut:
    return UserOut.from_domain(container.admin.set_user_active(admin, user_id, True))


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, admin: Admin, container: Container) -> UserOut:
    return UserOut.from_domain(container.admin.set_user_active(admin, user_id, False))


@router.patch("/technicians/{user_id}", response_model=UserOut)
def update_technician(user_id: int, body: TechnicianProfileUpdate, admin: Admin, container: Container) -> UserOut:
    return UserOut.from_domain(container.admin.update_technician(admin, user_id, **body.model_dump(exclude_none=True)))


# --- services -------------------------------------------------------------------------------


@router.get("/services", response_model=list[ServiceOut])
def list_services(admin: Admin, container: Container) -> list[ServiceOut]:
    return [presenters.service(s) for s in container.admin.list_services()]


@router.post("/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(body: ServiceIn, admin: Admin, container: Container) -> ServiceOut:
    return presenters.service(container.admin.create_service(admin, **body.model_dump()))


@router.patch("/services/{service_id}", response_model=ServiceOut)
def update_service(service_id: int, body: ServiceUpdate, admin: Admin, container: Container) -> ServiceOut:
    return presenters.service(container.admin.update_service(admin, service_id, **body.model_dump(exclude_none=True)))


@router.put("/services/{service_id}/dependencies", response_model=ServiceOut)
def set_dependencies(service_id: int, body: DependenciesIn, admin: Admin, container: Container) -> ServiceOut:
    return presenters.service(container.admin.set_dependencies(admin, service_id, set(body.depends_on)))


# --- categories -----------------------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(admin: Admin, container: Container) -> list[CategoryOut]:
    return [presenters.category(c) for c in container.admin.list_categories()]


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, admin: Admin, container: Container) -> CategoryOut:
    return presenters.category(container.admin.create_category(admin, **body.model_dump()))


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, body: CategoryUpdate, admin: Admin, container: Container) -> CategoryOut:
    return presenters.category(
        container.admin.update_category(admin, category_id, **body.model_dump(exclude_none=True))
    )


# --- SLA policies ---------------------------------------------------------------------------


@router.get("/sla-policies", response_model=list[PolicyOut])
def list_policies(admin: Admin, container: Container) -> list[PolicyOut]:
    return [presenters.policy(p) for p in container.admin.list_policies(admin)]


@router.post("/sla-policies", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
def create_policy(body: PolicyIn, admin: Admin, container: Container) -> PolicyOut:
    return presenters.policy(container.admin.create_policy(admin, **body.model_dump()))


@router.put("/sla-policies/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: int, body: PolicyUpdate, admin: Admin, container: Container) -> PolicyOut:
    return presenters.policy(container.admin.update_policy(admin, policy_id, **body.model_dump()))


@router.delete("/sla-policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(policy_id: int, admin: Admin, container: Container) -> Response:
    container.admin.delete_policy(admin, policy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- settings ---------------------------------------------------------------------------------


@router.get("/settings/assignment-strategy", response_model=list[StrategyInfo])
def list_strategies(admin: Admin, container: Container) -> list[StrategyInfo]:
    return container.assignment.list_strategies()


@router.put("/settings/assignment-strategy", response_model=list[StrategyInfo])
def set_strategy(body: StrategyIn, admin: Admin, container: Container) -> list[StrategyInfo]:
    container.assignment.set_strategy(body.key, admin)
    return container.assignment.list_strategies()


@router.get("/settings/escalation", response_model=EscalationSettings)
def get_escalation(admin: Admin, container: Container) -> EscalationSettings:
    return EscalationSettings(include_p2=container.escalation.includes_p2())


@router.put("/settings/escalation", response_model=EscalationSettings)
def set_escalation(body: EscalationSettings, admin: Admin, container: Container) -> EscalationSettings:
    container.escalation.set_include_p2(body.include_p2, admin)
    return EscalationSettings(include_p2=container.escalation.includes_p2())


# --- monitoring -------------------------------------------------------------------------------


@router.get("/audit-logs", response_model=list[AuditRecordOut])
def audit_logs(
    admin: Admin,
    container: Container,
    incident_id: int | None = None,
    actor_id: int | None = None,
    action: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditRecordOut]:
    records = container.audit.recent(
        admin, limit=limit, offset=offset, incident_id=incident_id, actor_id=actor_id, action=action
    )
    return [presenters.audit_record(r) for r in records]


@router.get("/notifications", response_model=list[NotificationOut])
def delivery_log(
    admin: Admin, container: Container, limit: Annotated[int, Query(ge=1, le=500)] = 200
) -> list[NotificationOut]:
    """Every notification on every channel, incl. simulated e-mail/SMS and failures."""
    return [presenters.notification(n) for n in container.notifications.delivery_log(admin, limit)]


@router.post("/sla/check-now", response_model=SLACheckSummary)
def check_sla_now(admin: Admin, container: Container) -> SLACheckSummary:
    """Run one SLA-monitor pass immediately (handy in the demo instead of waiting 60 s)."""
    return container.sla.run_checks()
