"""In-process fan-out of live events to Server-Sent-Event subscribers.

Services run in worker threads (sync endpoints, the SLA monitor) while SSE
connections live on the asyncio loop, so publish() hands each message to the
subscriber's own loop with call_soon_threadsafe.
"""

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any

QUEUE_SIZE = 100


@dataclass(eq=False)
class Subscription:
    user_id: int
    is_staff: bool
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=QUEUE_SIZE))

    def wants(self, audience: frozenset[int]) -> bool:
        return self.is_staff or self.user_id in audience


class EventBroadcaster:
    def __init__(self) -> None:
        self._subscriptions: set[Subscription] = set()
        self._lock = threading.Lock()

    def subscribe(self, user_id: int, is_staff: bool) -> Subscription:
        """Call from inside the running event loop (the SSE endpoint)."""
        subscription = Subscription(user_id, is_staff, asyncio.get_running_loop())
        with self._lock:
            self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            self._subscriptions.discard(subscription)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscriptions)

    def publish(self, message: dict[str, Any], audience: frozenset[int]) -> None:
        """Staff receive everything; other users only messages about their own incidents."""
        with self._lock:
            targets = [s for s in self._subscriptions if s.wants(audience)]
        for subscription in targets:
            if not subscription.loop.is_closed():
                subscription.loop.call_soon_threadsafe(self._offer, subscription.queue, message)

    @staticmethod
    def _offer(queue: asyncio.Queue, message: dict[str, Any]) -> None:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            pass  # slow client: drop rather than block the publisher
