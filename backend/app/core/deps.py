"""FastAPI dependencies: per-request session/unit of work, current user, role guards."""

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.domain.enums import Permission
from app.domain.exceptions import InvalidTokenError, UnauthorizedOperationError
from app.domain.users import User
from app.repositories.sql_repositories import SqlAlchemyUnitOfWork
from app.services.container import Infrastructure, ServiceContainer, build_container

_bearer = HTTPBearer(auto_error=False)


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()  # anything not committed by a service is rolled back here


def get_infrastructure(request: Request) -> Infrastructure:
    return request.app.state.infra


def get_container(
    session: Annotated[Session, Depends(get_session)], infra: Annotated[Infrastructure, Depends(get_infrastructure)]
) -> ServiceContainer:
    return build_container(SqlAlchemyUnitOfWork(session, infra.clock), infra)


Container = Annotated[ServiceContainer, Depends(get_container)]


def get_current_user(
    container: Container, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidTokenError("Missing bearer token")
    return container.auth.authenticate(credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(*permissions: Permission) -> Callable[[User], User]:
    """Role guard: `user: Annotated[User, Depends(require(Permission.MANAGE_USERS))]`."""

    def guard(user: CurrentUser) -> User:
        missing = [p.value for p in permissions if not user.has_permission(p)]
        if missing:
            raise UnauthorizedOperationError(
                f"Your role ({user.role.value}) cannot perform this action", details={"missing_permissions": missing}
            )
        return user

    return guard
