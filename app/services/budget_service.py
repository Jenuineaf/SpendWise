import uuid
from decimal import Decimal

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.budget import Budget
from app.models.expense import Expense
from app.schemas.budget import BudgetCreate, BudgetRead, BudgetUpdate
from app.services.category_service import get_category


async def compute_spent(
    db: AsyncSession, owner_id: uuid.UUID, category_id: uuid.UUID, year: int, month: int
) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.owner_id == owner_id,
            Expense.category_id == category_id,
            extract("year", Expense.date) == year,
            extract("month", Expense.date) == month,
        )
    )
    return Decimal(result.scalar_one())


def _to_read(budget: Budget, spent: Decimal) -> BudgetRead:
    remaining = budget.amount - spent
    percent_used = float(spent / budget.amount * 100) if budget.amount else 0.0
    return BudgetRead(
        id=budget.id,
        category_id=budget.category_id,
        year=budget.year,
        month=budget.month,
        amount=budget.amount,
        spent=spent,
        remaining=remaining,
        percent_used=round(percent_used, 2),
        created_at=budget.created_at,
        updated_at=budget.updated_at,
    )


async def create_budget(db: AsyncSession, owner_id: uuid.UUID, data: BudgetCreate) -> BudgetRead:
    await get_category(db, owner_id, data.category_id)
    existing = await db.execute(
        select(Budget).where(
            Budget.owner_id == owner_id,
            Budget.category_id == data.category_id,
            Budget.year == data.year,
            Budget.month == data.month,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("Budget already set for this category and month")

    budget = Budget(owner_id=owner_id, **data.model_dump())
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    spent = await compute_spent(db, owner_id, budget.category_id, budget.year, budget.month)
    return _to_read(budget, spent)


async def _get_budget(db: AsyncSession, owner_id: uuid.UUID, budget_id: uuid.UUID) -> Budget:
    result = await db.execute(
        select(Budget).where(Budget.id == budget_id, Budget.owner_id == owner_id)
    )
    budget = result.scalar_one_or_none()
    if budget is None:
        raise NotFoundError("Budget not found")
    return budget


async def update_budget(
    db: AsyncSession, owner_id: uuid.UUID, budget_id: uuid.UUID, data: BudgetUpdate
) -> BudgetRead:
    budget = await _get_budget(db, owner_id, budget_id)
    budget.amount = data.amount
    await db.commit()
    await db.refresh(budget)
    spent = await compute_spent(db, owner_id, budget.category_id, budget.year, budget.month)
    return _to_read(budget, spent)


async def list_budgets(
    db: AsyncSession, owner_id: uuid.UUID, year: int | None = None, month: int | None = None
) -> list[BudgetRead]:
    filters = [Budget.owner_id == owner_id]
    if year is not None:
        filters.append(Budget.year == year)
    if month is not None:
        filters.append(Budget.month == month)
    result = await db.execute(
        select(Budget).where(*filters).order_by(Budget.year.desc(), Budget.month.desc())
    )
    budgets = list(result.scalars().all())
    reads = []
    for budget in budgets:
        spent = await compute_spent(db, owner_id, budget.category_id, budget.year, budget.month)
        reads.append(_to_read(budget, spent))
    return reads


async def delete_budget(db: AsyncSession, owner_id: uuid.UUID, budget_id: uuid.UUID) -> None:
    budget = await _get_budget(db, owner_id, budget_id)
    await db.delete(budget)
    await db.commit()
