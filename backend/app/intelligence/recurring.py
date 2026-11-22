"""Recurring problem detection: the same kind of incident keeps coming back on a service.

Over the last 30 days, per service, two incidents are "the same problem" when their TF-IDF similarity is
>= SIMILARITY. Groups are the connected components of that relation (single-link, via union-find), so A~B and
B~C put A, B and C together. A group with >= MIN_OCCURRENCES incidents spread over >= 24 h is a recurring
problem: a candidate for root-cause analysis instead of fixing the symptom again. (A burst within a day is
what duplicate detection and the correlation hotspot already cover.)
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.incident import Incident
from app.domain.service import ITService
from app.intelligence.text_similarity import TextSimilarity, incident_text

WINDOW = timedelta(days=30)
MIN_OCCURRENCES = 3
MIN_SPAN = timedelta(hours=24)
SIMILARITY = 0.25


@dataclass(frozen=True)
class RecurringProblem:
    service_id: int
    service: str
    title: str  # the most recent occurrence's title
    occurrences: int
    open_count: int
    incident_ids: tuple[int, ...]  # newest first
    first_seen: datetime
    last_seen: datetime
    latest_fix: str | None
    reason: str


class _DisjointSet:
    """Union-find over indexes 0..n-1 (path halving); groups similar incidents transitively."""

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, i: int) -> int:
        while self._parent[i] != i:
            self._parent[i] = self._parent[self._parent[i]]
            i = self._parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        self._parent[self.find(a)] = self.find(b)


class RecurringProblemDetector:
    def __init__(self, similarity: TextSimilarity) -> None:
        self._similarity = similarity

    def detect(
        self, services: Sequence[ITService], incidents: Sequence[Incident], now: datetime
    ) -> list[RecurringProblem]:
        names = {s.id: s.name for s in services}
        by_service: dict[int, list[Incident]] = defaultdict(list)
        for incident in incidents:
            if incident.service_id in names and now - incident.created_at <= WINDOW:
                by_service[incident.service_id].append(incident)
        problems = [
            self._describe(names[sid], group)
            for sid, members in by_service.items()
            for group in self._groups(members)
            if len(group) >= MIN_OCCURRENCES and self._spans_days(group)
        ]
        return sorted(problems, key=lambda p: (-p.open_count, -p.occurrences, -p.last_seen.timestamp()))

    def _groups(self, incidents: list[Incident]) -> list[list[Incident]]:
        texts = [incident_text(i.title, i.description) for i in incidents]
        sets = _DisjointSet(len(incidents))
        for a in range(len(incidents) - 1):
            for offset, score in enumerate(self._similarity.scores(texts[a], texts[a + 1 :]), start=a + 1):
                if score >= SIMILARITY:
                    sets.union(a, offset)
        groups: dict[int, list[Incident]] = defaultdict(list)
        for index, incident in enumerate(incidents):
            groups[sets.find(index)].append(incident)
        return list(groups.values())

    @staticmethod
    def _spans_days(group: list[Incident]) -> bool:
        """A burst within one day is a hotspot / duplicate cluster; recurring means it keeps coming back."""
        times = [i.created_at for i in group]
        return max(times) - min(times) >= MIN_SPAN

    @staticmethod
    def _describe(service: str, group: list[Incident]) -> RecurringProblem:
        newest_first = sorted(group, key=lambda i: i.created_at, reverse=True)
        fixes = [i.resolution_summary for i in newest_first if i.resolution_summary]
        open_count = sum(1 for i in group if i.status.is_open)
        days = max(1, (newest_first[0].created_at - newest_first[-1].created_at).days)
        reason = f"{len(group)} similar incidents on {service} within {days} day(s)"
        if fixes and open_count:
            reason += f"; it was fixed before but came back ({open_count} still open)"
        elif fixes:
            reason += "; the same fix was applied repeatedly - consider a permanent fix"
        return RecurringProblem(
            service_id=group[0].service_id,
            service=service,
            title=newest_first[0].title,
            occurrences=len(group),
            open_count=open_count,
            incident_ids=tuple(i.id for i in newest_first),
            first_seen=newest_first[-1].created_at,
            last_seen=newest_first[0].created_at,
            latest_fix=fixes[0] if fixes else None,
            reason=reason,
        )
