import math
import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DBSession
from app.schemas.expense import ExpenseCreate, ExpenseRead, ExpenseUpdate, PaginatedExpenses
from app.services import expense_service

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("", response_model=PaginatedExpenses)
async def list_expenses(
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    category_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    items, total = await expense_service.list_expenses(
        db, current_user.id, page, page_size, category_id, date_from, date_to
    )
    pages = math.ceil(total / page_size) if total else 0
    return PaginatedExpenses(items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(data: ExpenseCreate, current_user: CurrentUser, db: DBSession):
    return await expense_service.create_expense(db, current_user.id, data)


@router.get("/{expense_id}", response_model=ExpenseRead)
async def get_expense(expense_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    return await expense_service.get_expense(db, current_user.id, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseRead)
async def update_expense(
    expense_id: uuid.UUID, data: ExpenseUpdate, current_user: CurrentUser, db: DBSession
):
    return await expense_service.update_expense(db, current_user.id, expense_id, data)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await expense_service.delete_expense(db, current_user.id, expense_id)
