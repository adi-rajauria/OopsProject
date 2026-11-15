from app.domain.enums import ChannelType, Permission
from app.domain.exceptions import UnauthorizedOperationError
from app.domain.notification import Notification
from app.domain.repositories import UnitOfWork
from app.domain.users import User


class NotificationService:
    """Read side of notifications (the write side is the NotificationDispatcher observer)."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def inbox(self, user: User, *, unread_only: bool = False, limit: int = 50) -> list[Notification]:
        return self._uow.notifications.list_for_user(user.id, channel=ChannelType.IN_APP,
                                                     unread_only=unread_only, limit=limit)

    def unread_count(self, user: User) -> int:
        return len(self._uow.notifications.list_for_user(user.id, unread_only=True, limit=1000))

    def mark_read(self, user: User, notification_id: int) -> Notification:
        notification = self._uow.notifications.get(notification_id)
        if notification is None or notification.recipient_id != user.id:
            raise UnauthorizedOperationError("This notification does not belong to you")
        notification.mark_read()
        self._uow.notifications.update(notification)
        self._uow.commit()
        return notification

    def mark_all_read(self, user: User) -> int:
        unread = self._uow.notifications.list_for_user(user.id, unread_only=True, limit=1000)
        for notification in unread:
            notification.mark_read()
            self._uow.notifications.update(notification)
        self._uow.commit()
        return len(unread)

    def delivery_log(self, user: User, limit: int = 200) -> list[Notification]:
        """All channels incl. simulated e-mail/SMS - lets an admin show what was 'sent'."""
        if not user.has_permission(Permission.VIEW_AUDIT_LOG):
            raise UnauthorizedOperationError("Only administrators can view the delivery log")
        return self._uow.notifications.list_all(limit=limit)
