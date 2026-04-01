from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.user import User, UserRole
from app.schemas.dashboard import CategorySummary, DashboardSummary, MonthlyTrend, RecentTransaction
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


viewer_dependency = Depends(require_role(UserRole.viewer, UserRole.analyst, UserRole.admin))


@router.get("/summary", response_model=DashboardSummary, summary="High-level financial summary")
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = viewer_dependency,
) -> DashboardSummary:
    """Return income, expense, net balance, and record counts."""

    summary = await DashboardService.summary(db, current_user)
    return summary


@router.get("/by-category", response_model=list[CategorySummary], summary="Totals grouped by category")
async def dashboard_category(
    db: AsyncSession = Depends(get_db),
    current_user: User = viewer_dependency,
) -> list[CategorySummary]:
    """Return totals and percentages by category for the last 90 days."""

    return await DashboardService.by_category(db, current_user)


@router.get("/monthly-trend", response_model=list[MonthlyTrend], summary="Monthly income vs expenses")
async def dashboard_monthly_trend(
    db: AsyncSession = Depends(get_db),
    current_user: User = viewer_dependency,
) -> list[MonthlyTrend]:
    """Return the last 12 months of income and expense totals."""

    return await DashboardService.monthly_trend(db, current_user)


@router.get("/recent", response_model=list[RecentTransaction], summary="Recent transactions feed")
async def dashboard_recent(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = viewer_dependency,
) -> list[RecentTransaction]:
    """Return the N most recent transactions."""

    return await DashboardService.recent_transactions(db, current_user, limit=limit)
