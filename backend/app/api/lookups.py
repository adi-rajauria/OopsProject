"""Reference data any signed-in user needs (e.g. dropdowns on the report form)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api import presenters
from app.api.schemas import CategoryOut, Ref, ServiceOut
from app.core.deps import Container, CurrentUser, require
from app.domain.enums import Permission
from app.domain.users import User

router = APIRouter(prefix="/api/lookups", tags=["lookups"])


@router.get("/services", response_model=list[ServiceOut])
def services(user: CurrentUser, container: Container) -> list[ServiceOut]:
    return [presenters.service(s) for s in container.admin.list_services(active_only=True)]


@router.get("/categories", response_model=list[CategoryOut])
def categories(user: CurrentUser, container: Container) -> list[CategoryOut]:
    return [presenters.category(c) for c in container.admin.list_categories(active_only=True)]


@router.get("/technicians", response_model=list[Ref])
def technicians(
    user: Annotated[User, Depends(require(Permission.VIEW_ALL_INCIDENTS))], container: Container
) -> list[Ref]:
    return [
        Ref(id=t.id, name=t.full_name, code=t.display_code)
        for t in container.uow.users.list_technicians()
        if t.is_active
    ]
