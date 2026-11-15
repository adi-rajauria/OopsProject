from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import Container, require
from app.domain.enums import Permission
from app.domain.users import User
from app.services.report_service import Overview, ServiceStats, SLAReport, TechnicianStats, TrendPoint

router = APIRouter(prefix="/api/reports", tags=["reports"])
Manager = Annotated[User, Depends(require(Permission.VIEW_REPORTS))]


@router.get("/overview", response_model=Overview)
def overview(user: Manager, container: Container) -> Overview:
    return container.reports.overview(user)


@router.get("/technicians", response_model=list[TechnicianStats])
def technicians(user: Manager, container: Container) -> list[TechnicianStats]:
    return container.reports.technician_workload(user)


@router.get("/services", response_model=list[ServiceStats])
def services(user: Manager, container: Container) -> list[ServiceStats]:
    return container.reports.service_analysis(user)


@router.get("/sla", response_model=SLAReport)
def sla(user: Manager, container: Container) -> SLAReport:
    return container.reports.sla_report(user)


@router.get("/trends", response_model=list[TrendPoint])
def trends(user: Manager, container: Container, days: Annotated[int, Query(ge=1, le=90)] = 14) -> list[TrendPoint]:
    return container.reports.trends(user, days)
