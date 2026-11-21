from app.domain.clock import Clock
from app.domain.enums import IncidentStatus, Permission
from app.domain.exceptions import UnauthorizedOperationError
from app.domain.incident import Incident
from app.domain.repositories import UnitOfWork
from app.domain.users import User
from app.intelligence.category_classifier import CategorySuggester, CategorySuggestion, LabelledText
from app.intelligence.correlation import CorrelationReport, IncidentCorrelator
from app.intelligence.duplicate_detector import DuplicateCheck, DuplicateDetector
from app.intelligence.recommender import Recommendation, TechnicianRecommender
from app.intelligence.resolution_suggester import ResolutionSuggester, SuggestedResolution
from app.intelligence.resolution_time import ResolutionEstimate, ResolutionTimeEstimator
from app.intelligence.sla_risk import RiskLevel, SLARiskAnalyzer, SLARiskAssessment
from app.intelligence.text_similarity import TextSimilarity, incident_text
from app.services.assignment_service import AssignmentService

HISTORY_STATUSES = (IncidentStatus.RESOLVED, IncidentStatus.VERIFIED, IncidentStatus.CLOSED)


def _require_staff(user: User) -> None:
    if not user.has_permission(Permission.VIEW_ALL_INCIDENTS):
        raise UnauthorizedOperationError("Only support staff can use this feature")


class IntelligenceService:
    """Facade over the intelligent features; each algorithm lives in app/intelligence."""

    def __init__(
        self, uow: UnitOfWork, clock: Clock, similarity: TextSimilarity, assignment: AssignmentService
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._assignment = assignment
        self._categories = CategorySuggester(similarity)
        self._duplicates = DuplicateDetector(similarity)
        self._resolutions = ResolutionSuggester(similarity)
        self._resolution_time = ResolutionTimeEstimator()
        self._recommender = TechnicianRecommender()
        self._risk = SLARiskAnalyzer()
        self._correlator = IncidentCorrelator()

    # --- used while reporting (any user who can report) ------------------------------
    def suggest_category(self, title: str, description: str) -> list[CategorySuggestion]:
        history = [
            LabelledText(i.category_id, incident_text(i.title, i.description))
            for i in sorted(self._uow.incidents.list_all(), key=lambda i: i.created_at, reverse=True)
            if i.category_id is not None and i.status in HISTORY_STATUSES
        ]
        return self._categories.suggest(incident_text(title, description), self._uow.categories.list(True), history)

    def check_duplicates(
        self, *, title: str, description: str, service_id: int, reporter_id: int, exclude_id: int | None = None
    ) -> DuplicateCheck:
        now = self._clock.now()
        candidates = self._uow.incidents.recent_for_service(service_id, now - DuplicateDetector.CANDIDATE_WINDOW)
        return self._duplicates.check(
            title=title,
            description=description,
            reporter_id=reporter_id,
            candidates=candidates,
            now=now,
            exclude_id=exclude_id,
        )

    def self_help(self, title: str, description: str) -> list[SuggestedResolution]:
        """Fixes that worked for similar resolved incidents, shown to the reporter before they submit."""
        return self._resolutions.suggest_for_text(title, description, self._uow.incidents.list_all())

    def estimate_resolution(self, incident: Incident) -> ResolutionEstimate | None:
        """Typical time to resolve; the caller has already checked the viewer may see the incident."""
        category = self._uow.categories.get(incident.category_id) if incident.category_id else None
        return self._resolution_time.estimate(
            incident, self._uow.incidents.list_all(), category.name if category else None
        )

    # --- staff features --------------------------------------------------------------
    def recommend_technicians(self, incident: Incident, viewer: User) -> list[Recommendation]:
        _require_staff(viewer)
        category = self._uow.categories.get(incident.category_id) if incident.category_id else None
        return self._recommender.recommend(
            self._assignment.candidates_for(incident), category.code if category else None, incident.priority
        )

    def suggested_resolutions(self, incident: Incident, viewer: User) -> list[SuggestedResolution]:
        _require_staff(viewer)
        return self._resolutions.suggest(incident, self._uow.incidents.list_all())

    def sla_risks(self, viewer: User, minimum: RiskLevel = RiskLevel.MEDIUM) -> list[SLARiskAssessment]:
        _require_staff(viewer)
        return self._risk.rank(self._uow.incidents.list_unclosed(), self._clock.now(), minimum)

    def correlation(self, viewer: User) -> CorrelationReport:
        _require_staff(viewer)
        return self._correlator.analyse(self._uow.services.list(), self._uow.incidents.list_all(), self._clock.now())
