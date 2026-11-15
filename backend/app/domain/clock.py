from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Abstraction over 'now' so time-dependent rules (SLA, escalation) are testable."""

    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    """Normalise to UTC: SQLite drops tzinfo (naive = UTC); PostgreSQL returns the session time zone."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
