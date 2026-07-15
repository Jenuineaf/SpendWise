import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DBSession
from app.schemas.savings_goal import SavingsGoalCreate, SavingsGoalRead, SavingsGoalUpdate
from app.services import savings_goal_service

router = APIRouter(prefix="/savings-goals", tags=["savings-goals"])


@router.get("", response_model=list[SavingsGoalRead])
async def list_goals(current_user: CurrentUser, db: DBSession):
    return await savings_goal_service.list_goals(db, current_user)


@router.post("", response_model=SavingsGoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(data: SavingsGoalCreate, current_user: CurrentUser, db: DBSession):
    return await savings_goal_service.create_goal(db, current_user, data)


@router.patch("/{goal_id}", response_model=SavingsGoalRead)
async def update_goal(
    goal_id: uuid.UUID, data: SavingsGoalUpdate, current_user: CurrentUser, db: DBSession
):
    return await savings_goal_service.update_goal(db, current_user, goal_id, data)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(goal_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await savings_goal_service.delete_goal(db, current_user, goal_id)
