from dataclasses import replace

from app.domain.enums import ACTIVE_WORK_STATUSES, Permission
from app.domain.exceptions import UnauthorizedOperationError
from app.domain.incident import Incident
from app.domain.repositories import UnitOfWork
from app.domain.search import SearchCriteria, SearchPage, SortOrder
from app.domain.users import Technician, User


class SearchService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def search(self, viewer: User, criteria: SearchCriteria) -> SearchPage:
        """Employees are always scoped to their own incidents, whatever they ask for."""
        if not viewer.has_permission(Permission.VIEW_ALL_INCIDENTS):
            criteria = replace(criteria, reporter_id=viewer.id)
        return self._uow.incidents.search(criteria)

    def technician_queue(self, technician: User) -> list[Incident]:
        if not isinstance(technician, Technician):
            raise UnauthorizedOperationError("Only technicians have a work queue")
        criteria = SearchCriteria(
            technician_id=technician.id, statuses=tuple(ACTIVE_WORK_STATUSES), sort=SortOrder.PRIORITY, page_size=100
        )
        return self._uow.incidents.search(criteria).items
