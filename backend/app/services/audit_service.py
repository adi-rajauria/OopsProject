from app.domain.audit import AuditRecord
from app.domain.enums import Permission
from app.domain.exceptions import UnauthorizedOperationError
from app.domain.repositories import UnitOfWork
from app.domain.users import User

MAX_PAGE = 500


class AuditService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def recent(
        self,
        viewer: User,
        *,
        limit: int = 100,
        offset: int = 0,
        incident_id: int | None = None,
        actor_id: int | None = None,
        action: str | None = None,
    ) -> list[AuditRecord]:
        if not viewer.has_permission(Permission.VIEW_AUDIT_LOG):
            raise UnauthorizedOperationError("Only administrators can view the audit log")
        return self._uow.audit.list_recent(
            limit=min(max(limit, 1), MAX_PAGE),
            offset=max(offset, 0),
            incident_id=incident_id,
            actor_id=actor_id,
            action=action,
        )
