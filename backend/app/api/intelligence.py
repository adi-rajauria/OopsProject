from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.schemas import LinkOut, SelfHelpTip, TextPreview
from app.core.deps import Container, require
from app.domain.enums import Permission
from app.domain.users import User
from app.intelligence.category_classifier import CategorySuggestion
from app.intelligence.correlation import CorrelationReport
from app.intelligence.sla_risk import RiskLevel, SLARiskAssessment

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])
Reporter = Annotated[User, Depends(require(Permission.REPORT_INCIDENT))]
Staff = Annotated[User, Depends(require(Permission.VIEW_ALL_INCIDENTS))]


@router.post("/suggest-category", response_model=list[CategorySuggestion])
def suggest_category(body: TextPreview, user: Reporter, container: Container) -> list[CategorySuggestion]:
    """Live suggestion while the employee is typing the report."""
    return container.intelligence.suggest_category(body.title, body.description)


@router.post("/check-duplicates", response_model=list[LinkOut])
def check_duplicates(body: TextPreview, user: Reporter, container: Container) -> list[LinkOut]:
    """Preview of similar open incidents on the chosen service before submitting."""
    if body.service_id is None:
        return []
    check = container.intelligence.check_duplicates(
        title=body.title, description=body.description, service_id=body.service_id, reporter_id=user.id
    )
    return [
        LinkOut(
            incident_id=m.incident_id,
            number=m.number,
            title=m.title,
            status=m.status.value,
            similarity=m.similarity,
            link_type=m.link_type.value,
        )
        for m in check.matches
    ]


@router.post("/self-help", response_model=list[SelfHelpTip])
def self_help(body: TextPreview, user: Reporter, container: Container) -> list[SelfHelpTip]:
    """Fixes that worked for similar resolved incidents, so the reporter can try them before submitting."""
    return [
        SelfHelpTip(title=s.title, resolution=s.resolution, similarity=s.similarity)
        for s in container.intelligence.self_help(body.title, body.description)
    ]


@router.get("/sla-risk", response_model=list[SLARiskAssessment])
def sla_risk(user: Staff, container: Container, minimum: RiskLevel = RiskLevel.MEDIUM) -> list[SLARiskAssessment]:
    return container.intelligence.sla_risks(user, minimum)


@router.get("/correlation", response_model=CorrelationReport)
def correlation(user: Staff, container: Container) -> CorrelationReport:
    return container.intelligence.correlation(user)
