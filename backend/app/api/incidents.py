from dataclasses import replace
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api import presenters
from app.api.csv_export import csv_response
from app.api.presenters import Directory
from app.api.schemas import (
    AnswerRequest,
    AssignRequest,
    AuditRecordOut,
    CloseRequest,
    CommentOut,
    CommentRequest,
    FeedbackOut,
    FeedbackRequest,
    IncidentCreate,
    IncidentDetailOut,
    IncidentSummaryOut,
    IncidentUpdate,
    QuestionRequest,
    Ref,
    ReopenRequest,
    ResolveRequest,
    SearchPageOut,
    VerifyRequest,
)
from app.core.deps import Container, CurrentUser, require
from app.domain.clock import ensure_utc
from app.domain.enums import IncidentStatus, Permission, Priority, SLAStatus
from app.domain.exceptions import InvalidInputError
from app.domain.factories import NewIncidentData
from app.domain.incident import Incident
from app.domain.search import MAX_PAGE_SIZE, SearchCriteria, SortOrder
from app.domain.users import User
from app.intelligence.recommender import Recommendation
from app.intelligence.resolution_suggester import SuggestedResolution
from app.intelligence.resolution_time import ResolutionEstimate

router = APIRouter(prefix="/api/incidents", tags=["incidents"])
Staff = Annotated[User, Depends(require(Permission.VIEW_ALL_INCIDENTS))]


def _detail(container: Container, incident: Incident, viewer: User) -> IncidentDetailOut:
    return presenters.incident_detail(incident, viewer, Directory(container.uow), container.uow, container.clock.now())


def _parse_number(number: str | None) -> int | None:
    if number is None or not number.strip():
        return None
    value = number.strip()
    incident_id = int(value) - 1000 if value.isdigit() and int(value) > 1000 else Incident.id_from_number(value)
    if incident_id is None:
        raise InvalidInputError("Incident number must look like INC1001", details={"field": "number"})
    return incident_id


@router.post("", response_model=IncidentDetailOut, status_code=status.HTTP_201_CREATED)
def report_incident(
    body: IncidentCreate, user: Annotated[User, Depends(require(Permission.REPORT_INCIDENT))], container: Container
) -> IncidentDetailOut:
    data = NewIncidentData(
        title=body.title,
        description=body.description,
        service_id=body.service_id,
        impact=body.impact,
        urgency=body.urgency,
        affected_users=body.affected_users,
        category_id=body.category_id,
    )
    return _detail(container, container.incidents.report(user, data, force=body.force), user)


def search_criteria(
    number: str | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    status_: Annotated[list[IncidentStatus] | None, Query(alias="status")] = None,
    priority: Annotated[list[Priority] | None, Query()] = None,
    category_id: Annotated[list[int] | None, Query()] = None,
    service_id: Annotated[list[int] | None, Query()] = None,
    technician_id: int | None = None,
    unassigned: bool = False,
    sla_status: Annotated[list[SLAStatus] | None, Query()] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    reporter_id: int | None = None,
    open_only: bool = False,
    sort: SortOrder = SortOrder.NEWEST,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchCriteria:
    """Query parameters -> search value object; shared by the list and the CSV export so they never drift apart."""
    return SearchCriteria(
        incident_id=_parse_number(number),
        text=q,
        statuses=tuple(status_ or ()),
        priorities=tuple(priority or ()),
        category_ids=tuple(category_id or ()),
        service_ids=tuple(service_id or ()),
        technician_id=technician_id,
        unassigned_only=unassigned,
        sla_statuses=tuple(sla_status or ()),
        created_from=ensure_utc(created_from),
        created_to=ensure_utc(created_to),
        reporter_id=reporter_id,
        open_only=open_only,
        sort=sort,
        page=page,
        page_size=page_size,
    )


Criteria = Annotated[SearchCriteria, Depends(search_criteria)]
EXPORT_COLUMNS = (
    "Number", "Title", "Status", "Priority", "Priority score", "Category", "Service", "Reporter", "Technician",
    "SLA status", "Response due", "Resolution due", "Escalation level", "Created", "Last update",
)


@router.get("", response_model=SearchPageOut)
def search_incidents(user: CurrentUser, container: Container, criteria: Criteria) -> SearchPageOut:
    result = container.search.search(user, criteria)
    directory, now = Directory(container.uow), container.clock.now()
    return SearchPageOut(
        items=[presenters.incident_summary(i, directory, now) for i in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
    )


@router.get("/export.csv", response_class=Response)
def export_incidents(user: CurrentUser, container: Container, criteria: Criteria) -> Response:
    """Every incident matching the filters (all pages), with the same visibility rules as the search."""
    directory, now = Directory(container.uow), container.clock.now()
    rows, page = [], 1
    while True:
        result = container.search.search(user, replace(criteria, page=page, page_size=MAX_PAGE_SIZE))
        rows += [_export_row(presenters.incident_summary(i, directory, now)) for i in result.items]
        if page >= result.pages:
            break
        page += 1
    return csv_response(f"incidents-{now:%Y%m%d-%H%M}.csv", EXPORT_COLUMNS, rows)


def _export_row(s: IncidentSummaryOut) -> tuple[object, ...]:
    def name(ref: Ref | None) -> str | None:
        return ref.name if ref else None

    return (
        s.number, s.title, s.status, s.priority, s.priority_score, name(s.category), name(s.service),
        name(s.reporter), name(s.technician), s.sla_status, s.response_due_at, s.resolution_due_at,
        s.escalation_level, s.created_at, s.updated_at,
    )


@router.get("/{incident_id}", response_model=IncidentDetailOut)
def get_incident(incident_id: int, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.get(incident_id, user), user)


@router.patch("/{incident_id}", response_model=IncidentDetailOut)
def update_incident(
    incident_id: int, body: IncidentUpdate, user: CurrentUser, container: Container
) -> IncidentDetailOut:
    incident = container.incidents.update_details(incident_id, user, **body.model_dump(exclude_none=True))
    return _detail(container, incident, user)


@router.post("/{incident_id}/assign", response_model=IncidentDetailOut)
def assign(incident_id: int, body: AssignRequest, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.assign(incident_id, body.technician_id, user), user)


@router.post("/{incident_id}/auto-assign", response_model=IncidentDetailOut)
def auto_assign(incident_id: int, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.auto_assign(incident_id, user), user)


@router.post("/{incident_id}/acknowledge", response_model=IncidentDetailOut)
def acknowledge(incident_id: int, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.acknowledge(incident_id, user), user)


@router.post("/{incident_id}/start", response_model=IncidentDetailOut)
def start_work(incident_id: int, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.start_work(incident_id, user), user)


@router.post("/{incident_id}/request-info", response_model=IncidentDetailOut)
def request_info(incident_id: int, body: QuestionRequest, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.request_info(incident_id, user, body.question), user)


@router.post("/{incident_id}/provide-info", response_model=IncidentDetailOut)
def provide_info(incident_id: int, body: AnswerRequest, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.provide_info(incident_id, user, body.answer), user)


@router.post("/{incident_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(incident_id: int, body: CommentRequest, user: CurrentUser, container: Container) -> CommentOut:
    comment = container.incidents.add_comment(incident_id, user, body.body, internal=body.internal)
    directory = Directory(container.uow)
    return CommentOut(
        id=comment.id,
        author=directory.user_ref(comment.author_id),
        kind=comment.kind.value,
        body=comment.body,
        is_internal=comment.is_internal,
        created_at=comment.created_at,
    )


@router.post("/{incident_id}/resolve", response_model=IncidentDetailOut)
def resolve(incident_id: int, body: ResolveRequest, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.resolve(incident_id, user, body.summary), user)


@router.post("/{incident_id}/reopen", response_model=IncidentDetailOut)
def reopen(incident_id: int, body: ReopenRequest, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.reopen(incident_id, user, body.reason), user)


@router.post("/{incident_id}/verify", response_model=IncidentDetailOut)
def verify(incident_id: int, body: VerifyRequest, user: CurrentUser, container: Container) -> IncidentDetailOut:
    incident = container.incidents.verify(incident_id, user, rating=body.rating, comment=body.comment)
    return _detail(container, incident, user)


@router.post("/{incident_id}/close", response_model=IncidentDetailOut)
def close(incident_id: int, body: CloseRequest, user: CurrentUser, container: Container) -> IncidentDetailOut:
    return _detail(container, container.incidents.close(incident_id, user, body.notes), user)


@router.post("/{incident_id}/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def feedback(incident_id: int, body: FeedbackRequest, user: CurrentUser, container: Container) -> FeedbackOut:
    fb = container.incidents.submit_feedback(incident_id, user, body.rating, body.comment)
    return FeedbackOut(rating=fb.rating, comment=fb.comment, created_at=fb.created_at)


@router.get("/{incident_id}/audit", response_model=list[AuditRecordOut])
def audit_trail(incident_id: int, user: CurrentUser, container: Container) -> list[AuditRecordOut]:
    return [presenters.audit_record(r) for r in container.incidents.audit_trail(incident_id, user)]


@router.get("/{incident_id}/recommendations", response_model=list[Recommendation])
def recommendations(incident_id: int, user: Staff, container: Container) -> list[Recommendation]:
    return container.intelligence.recommend_technicians(container.incidents.get(incident_id, user), user)


@router.get("/{incident_id}/resolution-estimate", response_model=ResolutionEstimate | None)
def resolution_estimate(incident_id: int, user: CurrentUser, container: Container) -> ResolutionEstimate | None:
    """Anyone who may view the incident (incl. its reporter) sees the typical time to resolve."""
    return container.intelligence.estimate_resolution(container.incidents.get(incident_id, user))


@router.get("/{incident_id}/suggested-resolutions", response_model=list[SuggestedResolution])
def suggested_resolutions(incident_id: int, user: Staff, container: Container) -> list[SuggestedResolution]:
    return container.intelligence.suggested_resolutions(container.incidents.get(incident_id, user), user)
