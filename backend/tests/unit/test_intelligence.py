"""The five intelligent features + resolution suggestion, tested as pure algorithms."""

from datetime import timedelta

import pytest

from app.domain.category import Category
from app.domain.enums import IncidentStatus, LinkType, Priority
from app.domain.incident import Incident
from app.domain.service import ITService
from app.domain.sla import IncidentSLA, SLAPolicy
from app.domain.strategies.assignment import TechnicianCandidate
from app.domain.users import Technician, TechnicianProfile
from app.intelligence.category_classifier import CategorySuggester, LabelledText
from app.intelligence.correlation import Health, IncidentCorrelator
from app.intelligence.duplicate_detector import DuplicateDetector
from app.intelligence.escalation import EscalationPolicy
from app.intelligence.recommender import TechnicianRecommender
from app.intelligence.recurring import RecurringProblemDetector
from app.intelligence.resolution_suggester import ResolutionSuggester
from app.intelligence.resolution_time import ResolutionTimeEstimator
from app.intelligence.sla_risk import RiskLevel, SLARiskAnalyzer
from app.intelligence.text_similarity import TfidfTextSimilarity, incident_text
from tests.conftest import START

SIM = TfidfTextSimilarity()


def incident(
    iid: int,
    title: str,
    description: str = "Details of the problem reported here.",
    *,
    reporter: int = 1,
    service: int = 1,
    age_min: float = 10,
    status=IncidentStatus.ASSIGNED,
    priority=Priority.P2,
    response=15,
    resolution=120,
    assignee: int | None = 7,
    summary: str | None = None,
    category: int | None = None,
) -> Incident:
    created = START - timedelta(minutes=age_min)
    sla = IncidentSLA.from_policy(
        SLAPolicy(id=1, priority=priority, response_minutes=response, resolution_minutes=resolution), created
    )
    return Incident(
        id=iid,
        title=title,
        description=description,
        reporter_id=reporter,
        service_id=service,
        impact=2,
        urgency=2,
        created_at=created,
        status=status,
        priority=priority,
        sla=sla,
        assigned_technician_id=assignee,
        resolution_summary=summary,
        category_id=category,
    )


# --- TF-IDF similarity --------------------------------------------------------------------------


def test_tfidf_similarity_relates_the_spec_payment_examples_but_not_unrelated_text():
    query = incident_text("Payment application unavailable", "Users cannot complete transactions")
    docs = [
        incident_text("Payment transaction failing", "Checkout errors when paying by card"),
        incident_text("Unable to make payment", "The payment page does not load"),
        incident_text("Printer on floor 3 jams", "Paper jam error on the HP printer"),
    ]
    related_a, related_b, unrelated = SIM.scores(query, docs)
    assert related_a >= DuplicateDetector.RELATED_THRESHOLD and related_b >= DuplicateDetector.RELATED_THRESHOLD
    assert unrelated < 0.1
    assert SIM.scores("", ["anything"]) == [0.0] and SIM.scores("x", []) == []


# --- Feature 1: duplicate detection -------------------------------------------------------------


def test_duplicate_detector_classifies_and_only_blocks_own_recent_duplicates():
    detector = DuplicateDetector(SIM)
    text = dict(
        title="Payment application unavailable",
        description="The payment application is unavailable and users cannot complete transactions",
    )
    candidates = [
        incident(1, **text, reporter=5, age_min=10),  # same reporter, 10 min ago
        incident(2, **text, reporter=6, age_min=10),  # other reporter
        incident(3, "Payment transaction failing", "Checkout fails with an error", age_min=20),
        incident(4, "Printer jams", "Paper jam on the 3rd floor printer", age_min=5),
        incident(5, **text, reporter=5, age_min=60 * 25),  # older than 24 h
        incident(6, **text, reporter=5, age_min=5, status=IncidentStatus.CLOSED),
    ]
    check = detector.check(**text, reporter_id=5, candidates=candidates, now=START)
    by_id = {m.incident_id: m for m in check.matches}
    assert set(by_id) == {1, 2, 3}
    assert by_id[1].link_type is LinkType.DUPLICATE and by_id[1].blocks_creation
    assert by_id[2].link_type is LinkType.DUPLICATE and not by_id[2].blocks_creation
    assert by_id[3].link_type is LinkType.RELATED
    assert [m.incident_id for m in check.blocking] == [1]

    later = detector.check(**text, reporter_id=5, candidates=[incident(1, **text, reporter=5, age_min=31)], now=START)
    assert not later.blocking  # same-reporter window is 30 minutes


# --- Feature 5: category suggestion -------------------------------------------------------------

CATEGORIES = [
    Category(id=1, code="NETWORK", name="Network", keywords=["vpn", "wifi", "network"]),
    Category(id=2, code="HARDWARE", name="Hardware", keywords=["laptop", "printer"]),
    Category(id=3, code="AUTHENTICATION", name="Auth", keywords=["login", "sso", "password"]),
]


def test_category_suggestion_uses_keywords_and_history():
    suggester = CategorySuggester(SIM)
    [top, *_] = suggester.suggest("My VPN keeps dropping when working from home", CATEGORIES)
    assert top.code == "NETWORK" and top.matched_keywords == ("vpn",)
    history = [LabelledText(3, "Cannot sign in to the portal, it loops back to the sign in page")]
    [top, *_] = suggester.suggest("Sign in loops back to the sign in page on the portal", CATEGORIES, history)
    assert top.code == "AUTHENTICATION" and "similarity" in top.reason
    assert suggester.suggest("Something is weird today", CATEGORIES) == []


def test_new_category_is_suggested_immediately_without_code_changes():
    printing = Category(id=9, code="PRINTING", name="Printing", keywords=["toner", "print queue"])
    [top, *_] = CategorySuggester(SIM).suggest("Toner empty and the print queue is stuck", [*CATEGORIES, printing])
    assert top.code == "PRINTING"


# --- Feature 2: technician recommendation ---------------------------------------------------


def tech(tid, skills, years, available=True):
    return Technician(
        id=tid,
        email=f"t{tid}@corp.test",
        full_name=f"Tech {tid}",
        password_hash="x",
        created_at=START,
        profile=TechnicianProfile(skills=frozenset(skills), experience_years=years, is_available=available),
    )


def test_recommender_ranks_with_reasons_and_puts_ineligible_last():
    candidates = [
        TechnicianCandidate(tech(1, ["NETWORK"], 3), 1, 0),
        TechnicianCandidate(tech(2, ["DATABASE"], 15), 0, 0),
        TechnicianCandidate(tech(3, ["NETWORK"], 10), 2, 4),
        TechnicianCandidate(tech(4, ["NETWORK"], 20, available=False), 0, 5),
    ]
    ranked = TechnicianRecommender().recommend(candidates, "NETWORK", Priority.P3, top=4)
    assert [r.technician_id for r in ranked] == [3, 1, 2, 4]
    assert "has NETWORK skill" in ranked[0].reasons and not ranked[-1].eligible
    assert ranked[0].score == pytest.approx(sum(ranked[0].breakdown.values()))
    critical = TechnicianRecommender().recommend(candidates[:3], "NETWORK", Priority.P1)
    assert critical[0].breakdown["experience"] > ranked[0].breakdown["experience"]  # P1 values experience more


# --- Feature 3: SLA risk -------------------------------------------------------------------------


def test_sla_risk_levels():
    analyzer = SLARiskAnalyzer()
    fresh = incident(1, "Fresh", age_min=1, priority=Priority.P3, response=60, resolution=480)
    acked = incident(2, "Acked", age_min=70, priority=Priority.P2, response=15, resolution=120)
    acked.sla.mark_responded(START - timedelta(minutes=65))
    unassigned = incident(3, "Unassigned", age_min=10, priority=Priority.P2, assignee=None)
    late = incident(4, "Late P1 incident", age_min=30, priority=Priority.P1, response=5, resolution=30)
    levels = {a.incident_id: a.level for a in (analyzer.assess(i, START) for i in (fresh, acked, unassigned, late))}
    assert levels == {1: RiskLevel.LOW, 2: RiskLevel.MEDIUM, 3: RiskLevel.HIGH, 4: RiskLevel.BREACHED}
    assert [a.incident_id for a in analyzer.rank([fresh, acked, unassigned, late], START)] == [4, 3, 2]
    acked.sla.pause(START)
    assert analyzer.assess(acked, START) is None  # paused clocks are not at risk


# --- Feature 4: escalation -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("minutes_after_due", "level"), [(0, 0), (0.02, 1), (4.9, 1), (5, 2), (10, 3), (15, 4), (99, 4)]
)
def test_escalation_level_boundaries(minutes_after_due, level):
    p1 = incident(1, "Core switch down", age_min=0, priority=Priority.P1, response=5, resolution=30)
    now = p1.sla.response_due_at + timedelta(minutes=minutes_after_due)
    assert EscalationPolicy().due_level(p1, now) == level


def test_escalation_only_for_unacknowledged_configured_priorities():
    p1 = incident(1, "Switch down", age_min=60, priority=Priority.P1, response=5, resolution=30)
    p2 = incident(2, "Slow pages", age_min=60, priority=Priority.P2, response=15, resolution=120)
    acked = incident(3, "Acked", age_min=60, priority=Priority.P1, status=IncidentStatus.IN_PROGRESS)
    policy = EscalationPolicy()
    assert [s.name for s in policy.pending_steps(p1, START)] == [
        "Technician",
        "Team Lead",
        "System Administrator",
        "IT Manager",
    ]
    assert policy.due_level(p2, START) == 0 and policy.due_level(acked, START) == 0
    assert EscalationPolicy(frozenset({Priority.P1, Priority.P2})).due_level(p2, START) == 4


# --- Correlation (innovation) ------------------------------------------------------------------


def test_correlation_finds_hotspot_and_upstream_cause():
    services = [
        ITService(id=1, code="NET", name="Network", business_criticality=4),
        ITService(id=2, code="VPN", name="VPN", business_criticality=3, depends_on={1}),
        ITService(id=3, code="WIKI", name="Wiki", business_criticality=1),
    ]
    incidents = [incident(i, f"VPN down {i}", service=2, age_min=20) for i in (1, 2, 3)]
    incidents += [
        incident(4, "Switch flapping", service=1, age_min=30),
        incident(5, "Old wiki issue", service=3, age_min=600),
    ]
    report = IncidentCorrelator().analyse(services, incidents, START)
    health = {n.code: n.health for n in report.nodes}
    assert health == {"NET": Health.DEGRADED, "VPN": Health.HOTSPOT, "WIKI": Health.DEGRADED}
    kinds = {(f.kind, f.root_service) for f in report.findings}
    assert kinds == {("HOTSPOT", "VPN"), ("UPSTREAM_CAUSE", "Network")}
    assert report.finding_for(5) is None and report.edges == [(2, 1)]


# --- Recurring problems ------------------------------------------------------------------------


def test_recurring_problem_groups_similar_incidents_across_days_but_not_bursts():
    services = [ITService(id=1, code="VPN", name="VPN", business_criticality=3), ITService(id=2, code="PAY", name="Payments", business_criticality=4)]
    vpn = [
        incident(1, "VPN disconnects every 10 minutes", "Remote staff lose the VPN connection", age_min=12 * 1440, status=IncidentStatus.CLOSED, summary="Replaced the uplink"),
        incident(2, "VPN keeps disconnecting remote staff", "Remote staff are disconnected from the VPN again", age_min=6 * 1440, status=IncidentStatus.CLOSED, summary="Restarted the VPN concentrator"),
        incident(3, "VPN tunnel drops for remote staff", "The VPN tunnel keeps dropping for remote workers", age_min=240),
        incident(4, "Printer jams on floor 2", "Paper jam on every page", age_min=3 * 1440),  # same service, unrelated
        incident(5, "VPN drops again", "VPN disconnects for remote staff", age_min=45 * 1440),  # older than 30 days
    ]
    burst = [incident(10 + n, "Payment application unavailable", "Users cannot complete transactions", service=2, age_min=30 + n) for n in range(4)]
    [problem] = RecurringProblemDetector(SIM).detect(services, vpn + burst, START)
    assert problem.service == "VPN" and problem.incident_ids == (3, 2, 1)  # newest first; the burst is not recurring
    assert problem.occurrences == 3 and problem.open_count == 1
    assert problem.latest_fix == "Restarted the VPN concentrator" and "came back" in problem.reason
    assert RecurringProblemDetector(SIM).detect(services, vpn[:2], START) == []  # 2 < minimum of 3


# --- Suggested resolution (bonus) -------------------------------------------------------------


def test_resolution_suggestions_come_from_similar_resolved_incidents():
    current = incident(10, "VPN keeps disconnecting", "VPN tunnel drops for remote staff")
    history = [
        incident(
            1,
            "VPN disconnects every 10 minutes",
            "Remote staff lose the VPN tunnel",
            status=IncidentStatus.CLOSED,
            summary="Renewed the VPN gateway certificate",
        ),
        incident(2, "Printer jams", "Paper jam on floor 3", status=IncidentStatus.CLOSED, summary="Cleaned rollers"),
        incident(3, "VPN is slow", "VPN is slow today", status=IncidentStatus.IN_PROGRESS),
    ]
    suggestions = ResolutionSuggester(SIM).suggest(current, history)
    assert [s.incident_id for s in suggestions] == [1]
    assert suggestions[0].resolution == "Renewed the VPN gateway certificate"
    # self-service: the same search on text the employee is still typing, before any incident exists
    tips = ResolutionSuggester(SIM).suggest_for_text("VPN keeps disconnecting", "", history)
    assert [t.incident_id for t in tips] == [1]
    assert ResolutionSuggester(SIM).suggest_for_text("Coffee machine is empty", "", history) == []


# --- Predicted resolution time ------------------------------------------------------------------


def resolved(iid: int, worked_min: float, *, priority=Priority.P2, category: int | None = 1, paused_min: float = 0):
    """A resolved incident that took worked_min minutes of work plus paused_min waiting on the reporter."""
    done = incident(iid, f"Past {iid}", age_min=500, status=IncidentStatus.CLOSED, priority=priority, category=category)
    if paused_min:
        done.sla.pause(done.created_at)
        done.sla.resume(done.created_at + timedelta(minutes=paused_min))
    done.sla.mark_resolved(done.created_at + timedelta(minutes=worked_min + paused_min))
    return done


def test_resolution_estimate_uses_median_of_same_category_and_priority_excluding_pauses():
    current = incident(99, "Open one", age_min=10, category=1)
    history = [resolved(1, 60), resolved(2, 90, paused_min=600), resolved(3, 600), resolved(4, 5, category=2)]
    estimate = ResolutionTimeEstimator().estimate(current, history, "Network")
    assert estimate is not None and estimate.median_minutes == 90 and estimate.sample_size == 3
    assert estimate.basis == "P2 Network incidents" and "1.5 h" in estimate.reason
    assert estimate.expected_by == current.created_at + timedelta(minutes=90)


def test_resolution_estimate_falls_back_to_priority_then_to_nothing():
    current = incident(99, "Open one", age_min=10, category=1)
    history = [resolved(1, 30), resolved(2, 40, category=2), resolved(3, 50, category=3)]
    fallback = ResolutionTimeEstimator().estimate(current, history, "Network")
    assert fallback is not None and fallback.basis == "P2 incidents" and fallback.median_minutes == 40
    too_few = [resolved(1, 30), resolved(2, 40, priority=Priority.P1), resolved(3, 50)]
    assert ResolutionTimeEstimator().estimate(current, too_few) is None  # only 2 P2 samples
