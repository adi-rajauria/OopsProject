"""Feature 1: duplicate / related incident detection (TF-IDF + cosine similarity)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.enums import IncidentStatus, LinkType
from app.domain.incident import Incident
from app.intelligence.text_similarity import TextSimilarity, incident_text


@dataclass(frozen=True)
class SimilarIncident:
    incident_id: int
    number: str
    title: str
    status: IncidentStatus
    similarity: float
    link_type: LinkType
    same_reporter: bool
    blocks_creation: bool

    def as_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "number": self.number,
            "title": self.title,
            "status": self.status.value,
            "similarity": self.similarity,
            "link_type": self.link_type.value,
            "same_reporter": self.same_reporter,
        }


@dataclass(frozen=True)
class DuplicateCheck:
    matches: list[SimilarIncident]

    @property
    def blocking(self) -> list[SimilarIncident]:
        return [m for m in self.matches if m.blocks_creation]


class DuplicateDetector:
    """Compares a new report with not-closed incidents on the *same service* from the last 24 h.

    similarity >= 0.85 -> DUPLICATE; >= 0.18 -> RELATED (thresholds calibrated, docs/ALGORITHMS.md).
    A DUPLICATE from the same reporter within 30 minutes blocks creation (accidental double
    submit) unless forced; matches from other people are only linked, never blocked.
    """

    RELATED_THRESHOLD = 0.18
    DUPLICATE_THRESHOLD = 0.85
    CANDIDATE_WINDOW = timedelta(hours=24)
    SAME_REPORTER_WINDOW = timedelta(minutes=30)
    MAX_MATCHES = 5

    def __init__(self, similarity: TextSimilarity) -> None:
        self._similarity = similarity

    def check(
        self,
        *,
        title: str,
        description: str,
        reporter_id: int,
        candidates: Sequence[Incident],
        now: datetime,
        exclude_id: int | None = None,
    ) -> DuplicateCheck:
        pool = [
            c
            for c in candidates
            if c.id != exclude_id
            and c.status is not IncidentStatus.CLOSED
            and now - c.created_at <= self.CANDIDATE_WINDOW
        ]
        scores = self._similarity.scores(
            incident_text(title, description), [incident_text(c.title, c.description) for c in pool]
        )
        matches = [self._match(c, s, reporter_id, now) for c, s in zip(pool, scores) if s >= self.RELATED_THRESHOLD]
        matches.sort(key=lambda m: -m.similarity)
        return DuplicateCheck(matches[: self.MAX_MATCHES])

    def _match(self, candidate: Incident, score: float, reporter_id: int, now: datetime) -> SimilarIncident:
        link_type = LinkType.DUPLICATE if score >= self.DUPLICATE_THRESHOLD else LinkType.RELATED
        same_reporter = candidate.reporter_id == reporter_id
        blocks = (
            link_type is LinkType.DUPLICATE
            and same_reporter
            and now - candidate.created_at <= self.SAME_REPORTER_WINDOW
        )
        return SimilarIncident(
            candidate.id, candidate.number, candidate.title, candidate.status, score, link_type, same_reporter, blocks
        )
