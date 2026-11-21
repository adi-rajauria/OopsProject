"""Bonus feature (G): suggest resolutions that worked for similar past incidents."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.enums import IncidentStatus
from app.domain.incident import Incident
from app.intelligence.text_similarity import TextSimilarity, incident_text

RESOLVED = (IncidentStatus.RESOLVED, IncidentStatus.VERIFIED, IncidentStatus.CLOSED)


@dataclass(frozen=True)
class SuggestedResolution:
    incident_id: int
    number: str
    title: str
    resolution: str
    similarity: float


class ResolutionSuggester:
    MIN_SIMILARITY = 0.15
    TOP = 3

    def __init__(self, similarity: TextSimilarity) -> None:
        self._similarity = similarity

    def suggest(self, incident: Incident, history: Sequence[Incident]) -> list[SuggestedResolution]:
        """Fixes for an existing incident (staff view)."""
        others = [h for h in history if h.id != incident.id]
        return self.suggest_for_text(incident.title, incident.description, others)

    def suggest_for_text(self, title: str, description: str, history: Sequence[Incident]) -> list[SuggestedResolution]:
        """Fixes for text that is not an incident yet (self-service while an employee is typing a report)."""
        pool = [h for h in history if h.status in RESOLVED and h.resolution_summary]
        scores = self._similarity.scores(incident_text(title, description), [incident_text(h.title, h.description) for h in pool])
        ranked = sorted(((h, s) for h, s in zip(pool, scores) if s >= self.MIN_SIMILARITY), key=lambda p: -p[1])
        return [SuggestedResolution(h.id, h.number, h.title, h.resolution_summary, s) for h, s in ranked[: self.TOP]]
