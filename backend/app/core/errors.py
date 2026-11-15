"""Single place that maps the custom exception hierarchy onto HTTP responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    AssignmentError,
    AuthenticationError,
    ConflictError,
    InvalidInputError,
    InvalidStateTransitionError,
    ITSMError,
    MissingSLAConfigurationError,
    NotFoundError,
    NotificationDeliveryError,
    PersistenceError,
    UnauthorizedOperationError,
)

logger = logging.getLogger(__name__)

# Most specific first; the first isinstance match wins.
STATUS_BY_ERROR: tuple[tuple[type[ITSMError], int], ...] = (
    (AuthenticationError, 401),
    (UnauthorizedOperationError, 403),
    (NotFoundError, 404),
    (InvalidStateTransitionError, 409),
    (ConflictError, 409),
    (AssignmentError, 409),
    (InvalidInputError, 422),
    (MissingSLAConfigurationError, 422),
    (NotificationDeliveryError, 502),
    (PersistenceError, 503),
)


def status_for(error: ITSMError) -> int:
    return next((status for cls, status in STATUS_BY_ERROR if isinstance(error, cls)), 400)


def _body(code: str, message: str, details: dict | list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def handle_itsm_error(request: Request, exc: ITSMError) -> JSONResponse:
    status = status_for(exc)
    if status >= 500:
        logger.error("%s on %s %s: %s", exc.code, request.method, request.url.path, exc.message)
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
    return JSONResponse(_body(exc.code, exc.message, exc.details), status_code=status, headers=headers)


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(_body("INVALID_INPUT", "Request validation failed", {"fields": fields}), status_code=422)


async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(_body("INTERNAL_ERROR", "Unexpected server error"), status_code=500)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ITSMError, handle_itsm_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected)
