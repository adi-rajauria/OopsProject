import pytest

from app.domain.enums import Priority
from app.domain.exceptions import InvalidInputError, TechnicianUnavailableError
from app.domain.strategies.assignment import (
    AssignmentContext,
    AssignmentStrategy,
    AssignmentStrategyRegistry,
    ExperienceBasedStrategy,
    LoadBasedStrategy,
    RoundRobinStrategy,
    SkillBasedStrategy,
    TechnicianCandidate,
)
from app.domain.users import Technician, TechnicianProfile
from tests.conftest import START


def tech(tid: int, skills=(), years=1, available=True, max_workload=8) -> Technician:
    return Technician(
        id=tid,
        email=f"t{tid}@corp.test",
        full_name=f"Tech {tid}",
        password_hash="x",
        created_at=START,
        profile=TechnicianProfile(
            skills=frozenset(skills), experience_years=years, is_available=available, max_workload=max_workload
        ),
    )


def ctx(category="NETWORK", last=None) -> AssignmentContext:
    return AssignmentContext(
        service_id=1, category_code=category, priority=Priority.P2, last_assigned_technician_id=last
    )


CANDIDATES = [
    TechnicianCandidate(tech(1, ["NETWORK"], years=3), active_incidents=4),
    TechnicianCandidate(tech(2, ["NETWORK"], years=8), active_incidents=2, service_history=1),
    TechnicianCandidate(tech(3, ["DATABASE"], years=12), active_incidents=0),
    TechnicianCandidate(tech(4, ["NETWORK"], years=20, available=False), active_incidents=0),
]


def test_skill_based_picks_least_loaded_skilled_technician():
    decision = SkillBasedStrategy().choose(CANDIDATES, ctx())
    assert decision.technician.id == 2
    assert "NETWORK skill" in decision.reason


def test_skill_based_without_matching_skill_raises():
    with pytest.raises(TechnicianUnavailableError):
        SkillBasedStrategy().choose(CANDIDATES, ctx(category="HARDWARE"))


def test_load_based_ignores_skill_and_picks_lowest_load():
    assert LoadBasedStrategy().choose(CANDIDATES, ctx()).technician.id == 3


def test_round_robin_rotates_and_wraps_around():
    strategy = RoundRobinStrategy()
    assert strategy.choose(CANDIDATES, ctx(last=None)).technician.id == 1
    assert strategy.choose(CANDIDATES, ctx(last=1)).technician.id == 2
    assert strategy.choose(CANDIDATES, ctx(last=3)).technician.id == 1  # 4 unavailable -> wrap


def test_experience_based_prefers_most_experienced_skilled_technician():
    decision = ExperienceBasedStrategy().choose(CANDIDATES, ctx())
    assert decision.technician.id == 2  # 12-yr tech lacks NETWORK, 20-yr tech unavailable


def test_technicians_at_workload_limit_are_not_eligible():
    full = [TechnicianCandidate(tech(1, ["NETWORK"], max_workload=3), active_incidents=3)]
    with pytest.raises(TechnicianUnavailableError):
        LoadBasedStrategy().choose(full, ctx())


def test_registry_rejects_unknown_strategy_and_accepts_new_ones_without_code_changes():
    with pytest.raises(InvalidInputError):
        AssignmentStrategyRegistry.create("NOPE")

    @AssignmentStrategyRegistry.register
    class HighestIdStrategy(AssignmentStrategy):  # Open/Closed: a new class is all it takes
        key, name, description = "TEST_HIGHEST_ID", "Highest id", "test only"

        def _pick(self, eligible, context):
            return max(eligible, key=lambda c: c.technician.id), "highest id"

    try:
        assert AssignmentStrategyRegistry.create("TEST_HIGHEST_ID").choose(CANDIDATES, ctx()).technician.id == 3
    finally:
        AssignmentStrategyRegistry._strategies.pop("TEST_HIGHEST_ID")
