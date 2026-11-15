"""Technician assignment - Strategy pattern (+ Template Method + Registry).

AssignmentStrategy.choose() is a template method: it filters out technicians who
are unavailable or at their workload limit, then delegates the actual choice to
the subclass hook _pick(). Strategies register themselves with a decorator, so a
new strategy is one new class - no other code changes (Open/Closed).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import ClassVar

from app.domain.enums import Priority
from app.domain.exceptions import InvalidInputError, TechnicianUnavailableError
from app.domain.users import Technician


@dataclass(frozen=True)
class TechnicianCandidate:
    technician: Technician
    active_incidents: int
    service_history: int = 0  # incidents this technician resolved on the same service

    @property
    def eligible(self) -> bool:
        return self.technician.can_accept_more(self.active_incidents)

    @property
    def experience(self) -> int:
        return self.technician.profile.experience_years


@dataclass(frozen=True)
class AssignmentContext:
    service_id: int
    category_code: str | None
    priority: Priority | None
    last_assigned_technician_id: int | None = None


@dataclass(frozen=True)
class AssignmentDecision:
    technician: Technician
    strategy_key: str
    reason: str


class AssignmentStrategy(ABC):
    key: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]

    def choose(self, candidates: Sequence[TechnicianCandidate], context: AssignmentContext) -> AssignmentDecision:
        eligible = [c for c in candidates if c.eligible]
        if not eligible:
            raise TechnicianUnavailableError(
                "No technician is available: all are unavailable or at their workload limit"
            )
        chosen, reason = self._pick(eligible, context)
        return AssignmentDecision(chosen.technician, self.key, f"{self.name}: {reason}")

    @abstractmethod
    def _pick(
        self, eligible: list[TechnicianCandidate], context: AssignmentContext
    ) -> tuple[TechnicianCandidate, str]: ...


class AssignmentStrategyRegistry:
    _strategies: ClassVar[dict[str, type[AssignmentStrategy]]] = {}

    @classmethod
    def register(cls, strategy_cls: type[AssignmentStrategy]) -> type[AssignmentStrategy]:
        cls._strategies[strategy_cls.key] = strategy_cls
        return strategy_cls

    @classmethod
    def create(cls, key: str) -> AssignmentStrategy:
        try:
            return cls._strategies[key]()
        except KeyError:
            raise InvalidInputError(
                f"Unknown assignment strategy '{key}'", details={"available": sorted(cls._strategies)}
            ) from None

    @classmethod
    def available(cls) -> list[type[AssignmentStrategy]]:
        return list(cls._strategies.values())

    @classmethod
    def is_registered(cls, key: str) -> bool:
        return key in cls._strategies


def _skilled(eligible: list[TechnicianCandidate], category_code: str | None) -> list[TechnicianCandidate]:
    return [c for c in eligible if c.technician.has_skill(category_code)]


@AssignmentStrategyRegistry.register
class SkillBasedStrategy(AssignmentStrategy):
    key = "SKILL"
    name = "Skill-based"
    description = "Only technicians whose skills include the incident category; least loaded of those wins."

    def _pick(self, eligible, context):
        skilled = _skilled(eligible, context.category_code)
        if not skilled:
            raise TechnicianUnavailableError(
                f"No available technician has the {context.category_code} skill",
                details={"category": context.category_code},
            )
        best = min(skilled, key=lambda c: (c.active_incidents, -c.experience, c.technician.id))
        return (
            best,
            f"has {context.category_code} skill and the lowest load among skilled ({best.active_incidents} active)",
        )


@AssignmentStrategyRegistry.register
class LoadBasedStrategy(AssignmentStrategy):
    key = "LOAD"
    name = "Load-based"
    description = "Technician with the fewest active incidents, regardless of skill."

    def _pick(self, eligible, context):
        best = min(eligible, key=lambda c: (c.active_incidents, c.technician.id))
        limit = best.technician.profile.max_workload
        return best, f"lowest current workload ({best.active_incidents} of {limit} active)"


@AssignmentStrategyRegistry.register
class RoundRobinStrategy(AssignmentStrategy):
    key = "ROUND_ROBIN"
    name = "Round-robin"
    description = "Rotates through available technicians in id order, spreading work evenly."

    def _pick(self, eligible, context):
        ordered = sorted(eligible, key=lambda c: c.technician.id)
        last = context.last_assigned_technician_id
        best = next((c for c in ordered if last is not None and c.technician.id > last), ordered[0])
        after = f"after T{last}" if last is not None else "start of rotation"
        return best, f"next in rotation ({after})"


@AssignmentStrategyRegistry.register
class ExperienceBasedStrategy(AssignmentStrategy):
    key = "EXPERIENCE"
    name = "Experience-based"
    description = "Most experienced technician (skilled ones preferred), ties broken by service history and load."

    def _pick(self, eligible, context):
        skilled = _skilled(eligible, context.category_code)
        pool = skilled or eligible
        best = min(pool, key=lambda c: (-c.experience, -c.service_history, c.active_incidents, c.technician.id))
        skill_note = "skilled, " if skilled else "no skilled technician free, "
        return (
            best,
            f"{skill_note}most experienced ({best.experience} yrs, {best.service_history} past incidents on this service)",
        )


DEFAULT_STRATEGY_KEY = SkillBasedStrategy.key
