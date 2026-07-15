import uuid
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.savings_goal import SavingsGoal
from app.models.user import User
from app.schemas.savings_goal import SavingsGoalCreate, SavingsGoalRead, SavingsGoalUpdate
from app.services.analytics_service import monthly_trend


def _months_between(today: date, deadline: date) -> int:
    delta = relativedelta(deadline, today)
    months = delta.years * 12 + delta.months
    if delta.days > 0:
        months += 1
    return max(months, 0)


async def _to_read(db: AsyncSession, goal: SavingsGoal, user: User) -> SavingsGoalRead:
    """Progress is an estimate, not a tracked balance: SpendWise has no bank/savings
    account integration, so "saved so far" is inferred as
    (self-reported monthly income - recent average monthly spend) projected out to
    the goal's deadline. It's directional, not a ledger.
    """
    trend = await monthly_trend(db, user.id, months=3)
    avg_expense = (
        sum((point.total for point in trend), Decimal(0)) / len(trend) if trend else Decimal(0)
    )

    monthly_income = user.monthly_income
    estimated_savings = (monthly_income - avg_expense) if monthly_income is not None else Decimal(0)

    today = date.today()
    months_remaining = _months_between(today, goal.deadline)
    projected = estimated_savings * months_remaining if estimated_savings > 0 else Decimal(0)
    percent = float(projected / goal.target_amount * 100) if goal.target_amount else 0.0

    return SavingsGoalRead(
        id=goal.id,
        name=goal.name,
        target_amount=goal.target_amount,
        deadline=goal.deadline,
        created_at=goal.created_at,
        monthly_income=monthly_income,
        avg_monthly_expense=round(avg_expense, 2),
        estimated_monthly_savings=round(estimated_savings, 2),
        months_remaining=months_remaining,
        projected_savings=round(projected, 2),
        percent_of_target=round(min(percent, 999.0), 2),
        on_track=projected >= goal.target_amount,
    )


async def create_goal(db: AsyncSession, user: User, data: SavingsGoalCreate) -> SavingsGoalRead:
    goal = SavingsGoal(owner_id=user.id, **data.model_dump())
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return await _to_read(db, goal, user)


async def _get_goal(db: AsyncSession, owner_id: uuid.UUID, goal_id: uuid.UUID) -> SavingsGoal:
    result = await db.execute(
        select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.owner_id == owner_id)
    )
    goal = result.scalar_one_or_none()
    if goal is None:
        raise NotFoundError("Savings goal not found")
    return goal


async def list_goals(db: AsyncSession, user: User) -> list[SavingsGoalRead]:
    result = await db.execute(
        select(SavingsGoal).where(SavingsGoal.owner_id == user.id).order_by(SavingsGoal.deadline)
    )
    goals = list(result.scalars().all())
    return [await _to_read(db, goal, user) for goal in goals]


async def update_goal(
    db: AsyncSession, user: User, goal_id: uuid.UUID, data: SavingsGoalUpdate
) -> SavingsGoalRead:
    goal = await _get_goal(db, user.id, goal_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await db.commit()
    await db.refresh(goal)
    return await _to_read(db, goal, user)


async def delete_goal(db: AsyncSession, user: User, goal_id: uuid.UUID) -> None:
    goal = await _get_goal(db, user.id, goal_id)
    await db.delete(goal)
    await db.commit()
