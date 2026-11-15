from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditRecord:
    """Immutable history entry: timestamp, user, action, incident, previous/new state, description."""

    created_at: datetime
    action: str
    description: str
    actor_id: int | None = None  # None = SYSTEM
    actor_name: str = "SYSTEM"
    incident_id: int | None = None  # None = not incident-related (user/config change)
    previous_state: str | None = None
    new_state: str | None = None
    id: int | None = None


class AuditTrail:
    """Ordered, append-only collection of an incident's audit records.

    Iterable + sized so it behaves like a read-only sequence; there is no way to
    remove or edit a record once added.
    """

    def __init__(self, incident_id: int, records: Iterable[AuditRecord] = ()) -> None:
        self._incident_id = incident_id
        self._records: list[AuditRecord] = sorted(records, key=lambda r: (r.created_at, r.id or 0))

    @property
    def incident_id(self) -> int:
        return self._incident_id

    def append(self, record: AuditRecord) -> None:
        if record.incident_id != self._incident_id:
            raise ValueError("Record belongs to a different incident")
        self._records.append(record)

    def actions(self) -> list[str]:
        return [r.action for r in self._records]

    def state_changes(self) -> list[AuditRecord]:
        return [r for r in self._records if r.new_state and r.new_state != r.previous_state]

    def __iter__(self) -> Iterator[AuditRecord]:
        return iter(self._records)

    def __len__(self) -> int:
        return len(self._records)
