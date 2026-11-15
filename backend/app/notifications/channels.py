"""Notification channels. EmailChannel and SMSChannel are Adapters: they make the
simulated providers fit the NotificationChannel interface and translate provider
errors into NotificationDeliveryError."""

from app.domain.enums import ChannelType
from app.domain.exceptions import NotificationDeliveryError
from app.domain.notification import Notification, NotificationChannel
from app.domain.users import User
from app.notifications.providers import FakeSmsGateway, FakeSmtpProvider

SMS_MAX_LENGTH = 160


class InAppChannel(NotificationChannel):
    """The stored notification row *is* the in-app delivery (shown in the bell)."""

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.IN_APP

    def can_reach(self, recipient: User) -> bool:
        return True

    def deliver(self, notification: Notification, recipient: User) -> None:
        return None


class EmailChannel(NotificationChannel):
    def __init__(self, provider: FakeSmtpProvider) -> None:
        self._provider = provider  # adaptee

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.EMAIL

    def can_reach(self, recipient: User) -> bool:
        return bool(recipient.email)

    def deliver(self, notification: Notification, recipient: User) -> None:
        try:
            self._provider.send_mail(from_addr=self._provider.sender, to_addrs=[recipient.email],
                                     subject=f"[I-ITSM] {notification.title}", body_text=notification.body)
        except (ConnectionError, OSError) as exc:
            raise NotificationDeliveryError(f"Email delivery failed: {exc}") from exc


class SMSChannel(NotificationChannel):
    def __init__(self, gateway: FakeSmsGateway) -> None:
        self._gateway = gateway  # adaptee

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.SMS

    def can_reach(self, recipient: User) -> bool:
        return recipient.phone is not None

    def deliver(self, notification: Notification, recipient: User) -> None:
        text = f"{notification.title}: {notification.body}"[:SMS_MAX_LENGTH]
        try:
            response = self._gateway.dispatch({"msisdn": recipient.phone, "text": text})
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise NotificationDeliveryError(f"SMS delivery failed: {exc}") from exc
        if response.get("status") != "QUEUED":
            raise NotificationDeliveryError(f"SMS gateway rejected message: {response}")


class ChannelRegistry:
    """Looks channels up by type. A new mechanism (e.g. push) = new class + register()."""

    def __init__(self, channels: list[NotificationChannel] | None = None) -> None:
        self._channels: dict[ChannelType, NotificationChannel] = {}
        for channel in channels or []:
            self.register(channel)

    def register(self, channel: NotificationChannel) -> None:
        self._channels[channel.channel_type] = channel

    def get(self, channel_type: ChannelType) -> NotificationChannel | None:
        return self._channels.get(channel_type)
