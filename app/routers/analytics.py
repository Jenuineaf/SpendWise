from datetime import date

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DBSession
from app.schemas.analytics import (
    CategoryBreakdownItem,
    DailySpendPoint,
    MonthlyTrendPoint,
    TopMerchantItem,
)
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/monthly-trend", response_model=list[MonthlyTrendPoint])
async def monthly_trend(
    current_user: CurrentUser, db: DBSession, months: int = Query(default=6, ge=1, le=36)
):
    return await analytics_service.monthly_trend(db, current_user.id, months)


@router.get("/category-breakdown", response_model=list[CategoryBreakdownItem])
async def category_breakdown(
    current_user: CurrentUser,
    db: DBSession,
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
):
    return await analytics_service.category_breakdown(db, current_user.id, year, month)


@router.get("/top-merchants", response_model=list[TopMerchantItem])
async def top_merchants(
    current_user: CurrentUser,
    db: DBSession,
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
    limit: int = Query(default=10, ge=1, le=50),
):
    return await analytics_service.top_merchants(db, current_user.id, year, month, limit)


@router.get("/daily-spend", response_model=list[DailySpendPoint])
async def daily_spend(
    current_user: CurrentUser,
    db: DBSession,
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
):
    return await analytics_service.daily_spend(db, current_user.id, year, month)
