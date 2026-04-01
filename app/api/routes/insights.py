from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.user import User, UserRole
from app.schemas.insights import InsightReport, NLQueryRequest, NLQueryResponse
from app.services.insight_service import InsightService

router = APIRouter(prefix="/insights", tags=["insights"])

analyst_dependency = Depends(require_role(UserRole.analyst, UserRole.admin))


@router.get("/", response_model=InsightReport, summary="Insight report for the previous month")
async def insight_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = analyst_dependency,
) -> InsightReport:
    """Return AI-inspired financial insights and anomalies."""

    return await InsightService.generate_report(db, current_user)


@router.post("/query", response_model=NLQueryResponse, summary="Ask a natural language finance question")
async def insight_query(
    body: NLQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = analyst_dependency,
) -> NLQueryResponse:
    """Handle NL queries using the lightweight parser and aggregation engine."""

    return await InsightService.run_nl_query(db, current_user, body)
