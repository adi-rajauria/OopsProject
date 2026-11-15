from typing import Annotated

from fastapi import APIRouter, Depends

from app.api import presenters
from app.api.presenters import Directory
from app.api.schemas import AvailabilityIn, IncidentSummaryOut, UserOut
from app.core.deps import Container, require
from app.domain.enums import Permission
from app.domain.users import User
from app.services.report_service import TechnicianStats

router = APIRouter(prefix="/api/technicians", tags=["technicians"])
Worker = Annotated[User, Depends(require(Permission.WORK_INCIDENTS))]


@router.get("/me/queue", response_model=list[IncidentSummaryOut])
def my_queue(user: Worker, container: Container) -> list[IncidentSummaryOut]:
    directory, now = Directory(container.uow), container.clock.now()
    return [presenters.incident_summary(i, directory, now) for i in container.search.technician_queue(user)]


@router.put("/me/availability", response_model=UserOut)
def set_availability(body: AvailabilityIn, user: Worker, container: Container) -> UserOut:
    return UserOut.from_domain(container.admin.set_own_availability(user, body.available))


@router.get("/workload", response_model=list[TechnicianStats])
def workload(
    user: Annotated[User, Depends(require(Permission.VIEW_ALL_INCIDENTS))], container: Container
) -> list[TechnicianStats]:
    return container.reports.technician_workload(user)
