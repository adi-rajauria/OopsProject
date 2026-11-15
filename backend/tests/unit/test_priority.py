import pytest

from app.domain.enums import Priority
from app.domain.exceptions import InvalidInputError
from app.domain.strategies.priority import PriorityInput, PriorityThresholds, WeightedPriorityCalculator

calc = WeightedPriorityCalculator()


def test_score_is_impact_times_urgency_times_criticality():
    result = calc.calculate(PriorityInput(impact=2, urgency=2, business_criticality=2, affected_users=1))
    assert result.score == 8
    assert result.priority is Priority.P3
    assert "impact 2 x urgency 2 x criticality 2 = 8" in result.explanation


@pytest.mark.parametrize(
    ("score", "expected"),
    [(64, Priority.P1), (32, Priority.P1), (31.99, Priority.P2), (16, Priority.P2),
     (15.99, Priority.P3), (6, Priority.P3), (5.99, Priority.P4), (1, Priority.P4)],
)
def test_priority_band_boundaries(score, expected):
    assert PriorityThresholds().band(score) is expected


@pytest.mark.parametrize(("users", "factor"), [(1, 1.0), (10, 1.0), (11, 1.25), (100, 1.25), (101, 1.5)])
def test_affected_users_factor_boundaries(users, factor):
    assert WeightedPriorityCalculator.users_factor(users) == factor


def test_many_affected_users_promote_priority():
    few = calc.calculate(PriorityInput(impact=3, urgency=3, business_criticality=3, affected_users=10))
    many = calc.calculate(PriorityInput(impact=3, urgency=3, business_criticality=3, affected_users=11))
    assert (few.priority, few.score) == (Priority.P2, 27)
    assert (many.priority, many.score) == (Priority.P1, 33.75)


def test_score_is_capped_at_64():
    result = calc.calculate(PriorityInput(impact=4, urgency=4, business_criticality=4, affected_users=5000))
    assert result.score == 64 and result.priority is Priority.P1


@pytest.mark.parametrize(
    "kwargs",
    [dict(impact=0, urgency=1, business_criticality=1), dict(impact=1, urgency=5, business_criticality=1),
     dict(impact=True, urgency=1, business_criticality=1), dict(impact=1, urgency=1, business_criticality=1,
                                                                affected_users=0)],
)
def test_invalid_priority_input_is_rejected(kwargs):
    with pytest.raises(InvalidInputError):
        PriorityInput(**kwargs)
