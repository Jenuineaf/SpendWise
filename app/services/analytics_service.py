import uuid
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.expense import Expense
from app.schemas.analytics import (
    CategoryBreakdownItem,
    DailySpendPoint,
    MonthlyTrendPoint,
    TopMerchantItem,
)


async def monthly_trend(
    db: AsyncSession, owner_id: uuid.UUID, months: int = 6
) -> list[MonthlyTrendPoint]:
    today = date.today()
    start = today.replace(day=1) - relativedelta(months=months - 1)

    year_col = extract("year", Expense.date).label("year")
    month_col = extract("month", Expense.date).label("month")
    result = await db.execute(
        select(year_col, month_col, func.sum(Expense.amount).label("total"))
        .where(Expense.owner_id == owner_id, Expense.date >= start)
        .group_by(year_col, month_col)
        .order_by(year_col, month_col)
    )
    return [
        MonthlyTrendPoint(year=int(row.year), month=int(row.month), total=row.total)
        for row in result.all()
    ]


async def category_breakdown(
    db: AsyncSession, owner_id: uuid.UUID, year: int, month: int
) -> list[CategoryBreakdownItem]:
    result = await db.execute(
        select(Category.id, Category.name, func.sum(Expense.amount).label("total"))
        .join(Expense, Expense.category_id == Category.id)
        .where(
            Expense.owner_id == owner_id,
            extract("year", Expense.date) == year,
            extract("month", Expense.date) == month,
        )
        .group_by(Category.id, Category.name)
        .order_by(func.sum(Expense.amount).desc())
    )
    rows = result.all()
    grand_total: Decimal = sum((row.total for row in rows), Decimal(0))

    items = []
    for row in rows:
        percent = float(row.total / grand_total * 100) if grand_total else 0.0
        items.append(
            CategoryBreakdownItem(
                category_id=row.id,
                category_name=row.name,
                total=row.total,
                percent=round(percent, 2),
            )
        )
    return items


async def top_merchants(
    db: AsyncSession, owner_id: uuid.UUID, year: int, month: int, limit: int = 10
) -> list[TopMerchantItem]:
    result = await db.execute(
        select(
            Expense.merchant,
            func.sum(Expense.amount).label("total"),
            func.count(Expense.id).label("count"),
        )
        .where(
            Expense.owner_id == owner_id,
            Expense.merchant.isnot(None),
            extract("year", Expense.date) == year,
            extract("month", Expense.date) == month,
        )
        .group_by(Expense.merchant)
        .order_by(func.sum(Expense.amount).desc())
        .limit(limit)
    )
    return [
        TopMerchantItem(merchant=row.merchant, total=row.total, count=row.count)
        for row in result.all()
    ]


async def daily_spend(
    db: AsyncSession, owner_id: uuid.UUID, year: int, month: int
) -> list[DailySpendPoint]:
    day_col = extract("day", Expense.date).label("day")
    result = await db.execute(
        select(day_col, func.sum(Expense.amount).label("total"))
        .where(
            Expense.owner_id == owner_id,
            extract("year", Expense.date) == year,
            extract("month", Expense.date) == month,
        )
        .group_by(day_col)
        .order_by(day_col)
    )
    return [DailySpendPoint(day=int(row.day), total=row.total) for row in result.all()]
