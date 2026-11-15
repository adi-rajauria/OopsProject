from typing import Annotated

from fastapi import APIRouter, Query

from app.api import presenters
from app.api.schemas import CountOut, NotificationOut
from app.core.deps import Container, CurrentUser

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def inbox(
    user: CurrentUser, container: Container, unread_only: bool = False, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[NotificationOut]:
    return [
        presenters.notification(n) for n in container.notifications.inbox(user, unread_only=unread_only, limit=limit)
    ]


@router.get("/unread-count", response_model=CountOut)
def unread_count(user: CurrentUser, container: Container) -> CountOut:
    return CountOut(count=container.notifications.unread_count(user))


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, user: CurrentUser, container: Container) -> NotificationOut:
    return presenters.notification(container.notifications.mark_read(user, notification_id))


@router.post("/read-all", response_model=CountOut)
def mark_all_read(user: CurrentUser, container: Container) -> CountOut:
    return CountOut(count=container.notifications.mark_all_read(user))
