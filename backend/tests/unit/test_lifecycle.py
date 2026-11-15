import pytest

from app.domain.enums import IncidentStatus as S
from app.domain.enums import Transition as T
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.lifecycle import state_for

EXPECTED_TRANSITIONS = {
    S.NEW: {T.CLASSIFY},
    S.CLASSIFIED: {T.ASSIGN},
    S.ASSIGNED: {T.ASSIGN, T.ACKNOWLEDGE},
    S.ACKNOWLEDGED: {T.START_WORK},
    S.IN_PROGRESS: {T.REQUEST_INFO, T.RESOLVE},
    S.PENDING_INFO: {T.PROVIDE_INFO},
    S.RESOLVED: {T.VERIFY, T.REOPEN, T.CLOSE},
    S.VERIFIED: {T.CLOSE},
    S.CLOSED: set(),
}


def test_happy_path_walks_the_full_lifecycle():
    state = state_for(S.NEW)
    path = [T.CLASSIFY, T.ASSIGN, T.ACKNOWLEDGE, T.START_WORK, T.REQUEST_INFO, T.PROVIDE_INFO,
            T.RESOLVE, T.VERIFY, T.CLOSE]
    visited = []
    for transition in path:
        state = state.apply(transition)
        visited.append(state.status)
    assert visited == [S.CLASSIFIED, S.ASSIGNED, S.ACKNOWLEDGED, S.IN_PROGRESS, S.PENDING_INFO,
                       S.IN_PROGRESS, S.RESOLVED, S.VERIFIED, S.CLOSED]


def test_new_to_closed_is_rejected():
    with pytest.raises(InvalidStateTransitionError) as err:
        state_for(S.NEW).close()
    assert err.value.current_state == "NEW" and err.value.action == "close"


@pytest.mark.parametrize("status", list(S))
def test_every_state_allows_exactly_the_designed_transitions(status):
    state = state_for(status)
    assert set(state.allowed_transitions()) == EXPECTED_TRANSITIONS[status]
    for transition in set(T) - EXPECTED_TRANSITIONS[status]:
        with pytest.raises(InvalidStateTransitionError):
            state.apply(transition)


def test_reopen_returns_resolved_incident_to_in_progress():
    assert state_for(S.RESOLVED).reopen().status is S.IN_PROGRESS
