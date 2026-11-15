"""Priority calculation - Strategy pattern.

IncidentService depends only on the PriorityCalculator abstraction; a different
algorithm (e.g. historical/ML-based) can be plugged in without touching it.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.enums import Priority
from app.domain.exceptions import InvalidInputError
from app.domain.validation import require_range


@dataclass(frozen=True)
class PriorityInput:
    impact: int  # 1 (single user) .. 4 (whole organisation)
    urgency: int  # 1 (can wait) .. 4 (work stopped)
    business_criticality: int  # 1 .. 4, taken from the affected service
    affected_users: int = 1

    def __post_init__(self) -> None:
        require_range(self.impact, "impact", 1, 4)
        require_range(self.urgency, "urgency", 1, 4)
        require_range(self.business_criticality, "business_criticality", 1, 4)
        if isinstance(self.affected_users, bool) or not isinstance(self.affected_users, int) or self.affected_users < 1:
            raise InvalidInputError("affected_users must be a positive integer", details={"field": "affected_users"})


@dataclass(frozen=True)
class PriorityResult:
    priority: Priority
    score: float
    explanation: str


class PriorityCalculator(ABC):
    @abstractmethod
    def calculate(self, data: PriorityInput) -> PriorityResult: ...


@dataclass(frozen=True)
class PriorityThresholds:
    """Single place for the score bands (inclusive lower bounds)."""

    p1: float = 32
    p2: float = 16
    p3: float = 6

    def band(self, score: float) -> Priority:
        if score >= self.p1:
            return Priority.P1
        if score >= self.p2:
            return Priority.P2
        if score >= self.p3:
            return Priority.P3
        return Priority.P4


class WeightedPriorityCalculator(PriorityCalculator):
    """score = impact x urgency x criticality x affected-users factor, capped at 64."""

    MAX_SCORE = 64.0
    # (upper bound of affected users, multiplier); ordered list = first match wins
    USER_FACTORS: tuple[tuple[float, float], ...] = ((10, 1.0), (100, 1.25), (float("inf"), 1.5))

    def __init__(self, thresholds: PriorityThresholds | None = None) -> None:
        self._thresholds = thresholds or PriorityThresholds()

    @classmethod
    def users_factor(cls, affected_users: int) -> float:
        return next(factor for limit, factor in cls.USER_FACTORS if affected_users <= limit)

    def calculate(self, data: PriorityInput) -> PriorityResult:
        base = data.impact * data.urgency * data.business_criticality
        factor = self.users_factor(data.affected_users)
        score = round(min(self.MAX_SCORE, base * factor), 2)
        priority = self._thresholds.band(score)
        explanation = (
            f"impact {data.impact} x urgency {data.urgency} x criticality {data.business_criticality} = {base}"
            f"; x{factor} for {data.affected_users} affected user(s) -> {score} => {priority.value} ({priority.label})"
        )
        return PriorityResult(priority, score, explanation)
