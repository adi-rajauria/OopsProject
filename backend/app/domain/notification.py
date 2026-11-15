from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.enums import ChannelType, NotificationType
from app.domain.users import User


class Notification:
    """A message to one user over one channel. Delivery outcome is recorded, not hidden."""

    def __init__(
        self,
        *,
        id: int | None,
        recipient_id: int,
        channel: ChannelType,
        type: NotificationType,
        title: str,
        body: str,
        created_at: datetime,
        incident_id: int | None = None,
        is_read: bool = False,
        delivered: bool = False,
        delivery_error: str | None = None,
    ) -> None:
        self._id = id
        self._recipient_id = recipient_id
        self._channel = ChannelType(channel)
        self._type = NotificationType(type)
        self._title = title
        self._body = body
        self._created_at = created_at
        self._incident_id = incident_id
        self._is_read = is_read
        self._delivered = delivered
        self._delivery_error = delivery_error

    @property
    def id(self) -> int | None:
        return self._id

    @property
    def recipient_id(self) -> int:
        return self._recipient_id

    @property
    def channel(self) -> ChannelType:
        return self._channel

    @property
    def type(self) -> NotificationType:
        return self._type

    @property
    def title(self) -> str:
        return self._title

    @property
    def body(self) -> str:
        return self._body

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def incident_id(self) -> int | None:
        return self._incident_id

    @property
    def is_read(self) -> bool:
        return self._is_read

    @property
    def delivered(self) -> bool:
        return self._delivered

    @property
    def delivery_error(self) -> str | None:
        return self._delivery_error

    def assign_id(self, new_id: int) -> None:
        self._id = new_id

    def mark_read(self) -> None:
        self._is_read = True

    def mark_delivered(self) -> None:
        self._delivered = True
        self._delivery_error = None

    def mark_failed(self, reason: str) -> None:
        self._delivered = False
        self._delivery_error = reason[:255]


class NotificationChannel(ABC):
    """Interface every delivery mechanism implements (in-app, email, SMS, ...).

    Implementations raise NotificationDeliveryError when the provider fails.
    """

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType: ...

    @abstractmethod
    def can_reach(self, recipient: User) -> bool: ...

    @abstractmethod
    def deliver(self, notification: Notification, recipient: User) -> None: ...
