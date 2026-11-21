from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.csv_export import csv_response
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


@router.get("/sla/violations.csv", response_class=Response)
def sla_violations_csv(user: Manager, container: Container) -> Response:
    report = container.reports.sla_report(user)
    rows = [
        (v.number, v.title, v.priority, v.status, v.service, v.technician, v.target.value, v.due_at, v.detected_at,
         v.overdue_minutes)
        for v in report.violations
    ]
    header = ("Number", "Title", "Priority", "Status", "Service", "Technician", "Target", "Due", "Detected",
              "Overdue (min)")
    return csv_response(f"sla-violations-{container.clock.now():%Y%m%d-%H%M}.csv", header, rows)


@router.get("/trends", response_model=list[TrendPoint])
def trends(user: Manager, container: Container, days: Annotated[int, Query(ge=1, le=90)] = 14) -> list[TrendPoint]:
    return container.reports.trends(user, days)
