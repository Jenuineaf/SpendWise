import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import AlertThreshold, BudgetAlert
from app.models.budget import Budget
from app.models.category import Category
from app.models.user import User
from app.schemas.alert import BudgetAlertRead
from app.services.budget_service import compute_spent
from app.services.email_service import send_email


async def check_and_trigger_alerts(
    db: AsyncSession, owner_id: uuid.UUID, category_id: uuid.UUID, expense_date: date
) -> None:
    """Fires at most one email per (budget, threshold) crossing, ever — the
    unique constraint on budget_id+threshold makes this idempotent, and since a
    Budget row is itself scoped to one (category, year, month), a new month
    naturally gets a fresh budget and fresh alert eligibility.
    """
    result = await db.execute(
        select(Budget).where(
            Budget.owner_id == owner_id,
            Budget.category_id == category_id,
            Budget.year == expense_date.year,
            Budget.month == expense_date.month,
        )
    )
    budget = result.scalar_one_or_none()
    if budget is None or budget.amount <= 0:
        return

    spent = await compute_spent(db, owner_id, category_id, budget.year, budget.month)
    percent_used = float(spent / budget.amount * 100)

    for threshold in (AlertThreshold.HUNDRED, AlertThreshold.EIGHTY):
        if percent_used < threshold.value:
            continue

        existing = await db.execute(
            select(BudgetAlert).where(
                BudgetAlert.budget_id == budget.id, BudgetAlert.threshold == threshold.value
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        db.add(BudgetAlert(owner_id=owner_id, budget_id=budget.id, threshold=threshold.value))
        await db.commit()

        category_result = await db.execute(select(Category.name).where(Category.id == category_id))
        category_name = category_result.scalar_one_or_none() or "this category"
        user_result = await db.execute(select(User.email).where(User.id == owner_id))
        user_email = user_result.scalar_one_or_none()

        if user_email:
            subject = f"SpendWise: {category_name} budget at {threshold.value}%"
            body = (
                f"You've spent {spent} of your {budget.amount} budget for {category_name} "
                f"this month ({budget.year}-{budget.month:02d}) — {round(percent_used, 1)}% used."
            )
            await send_email(user_email, subject, body)
        break  # only the highest threshold crossed in this pass gets emailed


async def list_alerts(db: AsyncSession, owner_id: uuid.UUID) -> list[BudgetAlertRead]:
    result = await db.execute(
        select(BudgetAlert, Category.name)
        .join(Budget, Budget.id == BudgetAlert.budget_id)
        .join(Category, Category.id == Budget.category_id)
        .where(BudgetAlert.owner_id == owner_id)
        .order_by(BudgetAlert.triggered_at.desc())
    )
    return [
        BudgetAlertRead(
            id=alert.id,
            budget_id=alert.budget_id,
            category_name=name,
            threshold=alert.threshold,
            triggered_at=alert.triggered_at,
        )
        for alert, name in result.all()
    ]
