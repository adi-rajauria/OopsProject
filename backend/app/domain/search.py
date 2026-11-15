from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import ceil

from app.domain.enums import IncidentStatus, Priority, SLAStatus
from app.domain.exceptions import InvalidInputError
from app.domain.incident import Incident

MAX_PAGE_SIZE = 100


class SortOrder(StrEnum):
    NEWEST = "-created_at"
    OLDEST = "created_at"
    PRIORITY = "priority"
    RECENTLY_UPDATED = "-updated_at"


@dataclass(frozen=True)
class SearchCriteria:
    """Value object describing an incident search. Every field is optional and
    criteria are combined with AND; multi-value fields mean 'any of'."""

    incident_id: int | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    statuses: tuple[IncidentStatus, ...] = ()
    priorities: tuple[Priority, ...] = ()
    category_ids: tuple[int, ...] = ()
    service_ids: tuple[int, ...] = ()
    technician_id: int | None = None
    unassigned_only: bool = False
    sla_statuses: tuple[SLAStatus, ...] = ()
    text: str | None = None
    reporter_id: int | None = None
    open_only: bool = False
    sort: SortOrder = SortOrder.NEWEST
    page: int = 1
    page_size: int = 20

    def __post_init__(self) -> None:
        if self.page < 1 or not 1 <= self.page_size <= MAX_PAGE_SIZE:
            raise InvalidInputError(f"page must be >= 1 and page_size between 1 and {MAX_PAGE_SIZE}")
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise InvalidInputError("created_from must not be after created_to")
        if self.text is not None and len(self.text) > 200:
            raise InvalidInputError("Search text is too long")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def text_term(self) -> str | None:
        return self.text.strip().lower() if self.text and self.text.strip() else None

    def matches(self, incident: Incident, sla_status: SLAStatus | None) -> bool:
        """Reference semantics (used by the in-memory repository; SQL mirrors it)."""
        checks = (
            self.incident_id is None or incident.id == self.incident_id,
            self.created_from is None or incident.created_at >= self.created_from,
            self.created_to is None or incident.created_at <= self.created_to,
            not self.statuses or incident.status in self.statuses,
            not self.priorities or incident.priority in self.priorities,
            not self.category_ids or incident.category_id in self.category_ids,
            not self.service_ids or incident.service_id in self.service_ids,
            self.technician_id is None or incident.assigned_technician_id == self.technician_id,
            not self.unassigned_only or incident.assigned_technician_id is None,
            not self.sla_statuses or sla_status in self.sla_statuses,
            self.reporter_id is None or incident.reporter_id == self.reporter_id,
            not self.open_only or incident.status.is_open,
            self.text_term is None or self.text_term in f"{incident.title} {incident.description}".lower(),
        )
        return all(checks)


@dataclass(frozen=True)
class SearchPage:
    items: list[Incident]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, ceil(self.total / self.page_size))
