import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DBSession
from app.schemas.recurring import RecurringRuleCreate, RecurringRuleRead, RecurringRuleUpdate
from app.services import recurring_service

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.get("", response_model=list[RecurringRuleRead])
async def list_rules(current_user: CurrentUser, db: DBSession):
    return await recurring_service.list_rules(db, current_user.id)


@router.post("", response_model=RecurringRuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(data: RecurringRuleCreate, current_user: CurrentUser, db: DBSession):
    return await recurring_service.create_rule(db, current_user.id, data)


@router.patch("/{rule_id}", response_model=RecurringRuleRead)
async def update_rule(
    rule_id: uuid.UUID, data: RecurringRuleUpdate, current_user: CurrentUser, db: DBSession
):
    return await recurring_service.update_rule(db, current_user.id, rule_id, data)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await recurring_service.delete_rule(db, current_user.id, rule_id)
