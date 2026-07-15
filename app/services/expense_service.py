import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.services.alert_service import check_and_trigger_alerts
from app.services.categorizer import learn_override
from app.services.category_service import get_category


async def create_expense(db: AsyncSession, owner_id: uuid.UUID, data: ExpenseCreate) -> Expense:
    await get_category(db, owner_id, data.category_id)
    expense = Expense(owner_id=owner_id, **data.model_dump())
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    await check_and_trigger_alerts(db, owner_id, expense.category_id, expense.date)
    return expense


async def get_expense(db: AsyncSession, owner_id: uuid.UUID, expense_id: uuid.UUID) -> Expense:
    result = await db.execute(
        select(Expense).where(Expense.id == expense_id, Expense.owner_id == owner_id)
    )
    expense = result.scalar_one_or_none()
    if expense is None:
        raise NotFoundError("Expense not found")
    return expense


async def list_expenses(
    db: AsyncSession,
    owner_id: uuid.UUID,
    page: int,
    page_size: int,
    category_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[Expense], int]:
    filters = [Expense.owner_id == owner_id]
    if category_id is not None:
        filters.append(Expense.category_id == category_id)
    if date_from is not None:
        filters.append(Expense.date >= date_from)
    if date_to is not None:
        filters.append(Expense.date <= date_to)

    count_result = await db.execute(select(func.count()).select_from(Expense).where(*filters))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Expense)
        .where(*filters)
        .order_by(Expense.date.desc(), Expense.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def update_expense(
    db: AsyncSession, owner_id: uuid.UUID, expense_id: uuid.UUID, data: ExpenseUpdate
) -> Expense:
    expense = await get_expense(db, owner_id, expense_id)
    updates = data.model_dump(exclude_unset=True)
    if "category_id" in updates:
        await get_category(db, owner_id, updates["category_id"])
    for field, value in updates.items():
        setattr(expense, field, value)
    await db.commit()
    await db.refresh(expense)

    if "category_id" in updates and expense.merchant:
        await learn_override(db, owner_id, expense.merchant, expense.category_id)

    if {"category_id", "amount", "date"} & updates.keys():
        await check_and_trigger_alerts(db, owner_id, expense.category_id, expense.date)

    return expense


async def delete_expense(db: AsyncSession, owner_id: uuid.UUID, expense_id: uuid.UUID) -> None:
    expense = await get_expense(db, owner_id, expense_id)
    await db.delete(expense)
    await db.commit()
