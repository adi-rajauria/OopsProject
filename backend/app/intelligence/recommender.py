"""Feature 2: smart technician recommendation with reasons (weighted multi-factor score).

Separate from the assignment strategies: strategies *decide*, the recommender
*explains and ranks* so an administrator can make an informed manual choice.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.enums import Priority
from app.domain.strategies.assignment import TechnicianCandidate

BASE_WEIGHTS = {"skill": 0.40, "workload": 0.25, "experience": 0.15, "service_history": 0.15, "availability": 0.05}
# Critical incidents value experience over spreading load.
CRITICAL_WEIGHTS = {**BASE_WEIGHTS, "workload": 0.15, "experience": 0.25}
EXPERIENCE_CAP_YEARS = 15
HISTORY_CAP = 5


@dataclass(frozen=True)
class Recommendation:
    technician_id: int
    name: str
    score: float  # 0..100
    eligible: bool
    reasons: tuple[str, ...]
    breakdown: dict[str, float]


class TechnicianRecommender:
    def recommend(
        self,
        candidates: Sequence[TechnicianCandidate],
        category_code: str | None,
        priority: Priority | None,
        top: int = 3,
    ) -> list[Recommendation]:
        weights = CRITICAL_WEIGHTS if priority in (Priority.P1, Priority.P2) else BASE_WEIGHTS
        ranked = sorted(
            (self._score(c, category_code, weights) for c in candidates),
            key=lambda r: (not r.eligible, -r.score, r.technician_id),
        )
        return ranked[:top]

    @staticmethod
    def _score(c: TechnicianCandidate, category_code: str | None, weights: dict[str, float]) -> Recommendation:
        profile = c.technician.profile
        factors = {
            "skill": 1.0 if c.technician.has_skill(category_code) else 0.0,
            "workload": max(0.0, 1 - c.active_incidents / profile.max_workload),
            "experience": min(profile.experience_years, EXPERIENCE_CAP_YEARS) / EXPERIENCE_CAP_YEARS,
            "service_history": min(c.service_history, HISTORY_CAP) / HISTORY_CAP,
            "availability": 1.0 if c.eligible else 0.0,
        }
        breakdown = {name: round(100 * weights[name] * value, 1) for name, value in factors.items()}
        reasons = [
            f"has {category_code} skill" if factors["skill"] else f"no {category_code or 'category'} skill",
            f"{c.active_incidents}/{profile.max_workload} active incidents",
            f"{profile.experience_years} yrs experience",
            f"resolved {c.service_history} incident(s) on this service",
        ]
        if not c.eligible:
            reasons.append("currently unavailable or at workload limit")
        return Recommendation(
            c.technician.id,
            c.technician.full_name,
            round(sum(breakdown.values()), 1),
            c.eligible,
            tuple(reasons),
            breakdown,
        )
