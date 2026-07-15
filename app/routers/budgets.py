import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DBSession
from app.schemas.budget import BudgetCreate, BudgetRead, BudgetUpdate
from app.services import budget_service

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetRead])
async def list_budgets(
    current_user: CurrentUser,
    db: DBSession,
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
):
    return await budget_service.list_budgets(db, current_user.id, year, month)


@router.post("", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
async def create_budget(data: BudgetCreate, current_user: CurrentUser, db: DBSession):
    return await budget_service.create_budget(db, current_user.id, data)


@router.patch("/{budget_id}", response_model=BudgetRead)
async def update_budget(
    budget_id: uuid.UUID, data: BudgetUpdate, current_user: CurrentUser, db: DBSession
):
    return await budget_service.update_budget(db, current_user.id, budget_id, data)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(budget_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await budget_service.delete_budget(db, current_user.id, budget_id)
