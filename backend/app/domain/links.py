from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import LinkType


@dataclass(frozen=True)
class IncidentLink:
    """Association between two incidents found to be similar (duplicate detection).
    Stored once from the newer incident to the older one; read in both directions."""

    incident_id: int
    related_incident_id: int
    similarity: float
    link_type: LinkType
    created_at: datetime

    def other(self, incident_id: int) -> int:
        return self.related_incident_id if incident_id == self.incident_id else self.incident_id
