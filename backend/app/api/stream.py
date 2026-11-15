"""Server-Sent Events: live incident updates for dashboards and the notification bell.

EventSource cannot send an Authorization header, so the JWT comes as ?token=...
(documented trade-off in docs/SECURITY.md)."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.domain.enums import Permission
from app.domain.users import User
from app.repositories.sql_repositories import SqlAlchemyUnitOfWork
from app.services.container import build_container

router = APIRouter(prefix="/api/stream", tags=["realtime"])
KEEPALIVE_SECONDS = 15


def _authenticate(request: Request, token: str) -> User:
    infra = request.app.state.infra
    with request.app.state.session_factory() as session:
        return build_container(SqlAlchemyUnitOfWork(session, infra.clock), infra).auth.authenticate(token)


@router.get("/events")
async def events(request: Request, token: str = Query(min_length=10, max_length=2000)) -> StreamingResponse:
    user = await run_in_threadpool(_authenticate, request, token)
    broadcaster = request.app.state.infra.broadcaster
    subscription = broadcaster.subscribe(user.id, user.has_permission(Permission.VIEW_ALL_INCIDENTS))

    async def stream() -> AsyncIterator[str]:
        try:
            yield "retry: 3000\n\n"
            yield f"event: ready\ndata: {json.dumps({'user_id': user.id})}\n\n"
            while not await request.is_disconnected():
                try:
                    message = await asyncio.wait_for(subscription.queue.get(), timeout=KEEPALIVE_SECONDS)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {message['type']}\ndata: {json.dumps(message)}\n\n"
        finally:
            broadcaster.unsubscribe(subscription)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
