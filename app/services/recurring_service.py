import uuid
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.expense import Expense
from app.models.recurring import Cadence, RecurringExpenseRule
from app.schemas.recurring import RecurringRuleCreate, RecurringRuleUpdate
from app.services.category_service import get_category

_MAX_CATCHUP_CYCLES = 366


def _advance(current: date, cadence: Cadence) -> date:
    if cadence == Cadence.DAILY:
        return current + timedelta(days=1)
    if cadence == Cadence.WEEKLY:
        return current + timedelta(weeks=1)
    if cadence == Cadence.MONTHLY:
        return current + relativedelta(months=1)
    return current + relativedelta(years=1)


async def create_rule(
    db: AsyncSession, owner_id: uuid.UUID, data: RecurringRuleCreate
) -> RecurringExpenseRule:
    await get_category(db, owner_id, data.category_id)
    rule = RecurringExpenseRule(owner_id=owner_id, **data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def list_rules(db: AsyncSession, owner_id: uuid.UUID) -> list[RecurringExpenseRule]:
    result = await db.execute(
        select(RecurringExpenseRule)
        .where(RecurringExpenseRule.owner_id == owner_id)
        .order_by(RecurringExpenseRule.next_run)
    )
    return list(result.scalars().all())


async def _get_rule(
    db: AsyncSession, owner_id: uuid.UUID, rule_id: uuid.UUID
) -> RecurringExpenseRule:
    result = await db.execute(
        select(RecurringExpenseRule).where(
            RecurringExpenseRule.id == rule_id, RecurringExpenseRule.owner_id == owner_id
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise NotFoundError("Recurring rule not found")
    return rule


async def update_rule(
    db: AsyncSession, owner_id: uuid.UUID, rule_id: uuid.UUID, data: RecurringRuleUpdate
) -> RecurringExpenseRule:
    rule = await _get_rule(db, owner_id, rule_id)
    updates = data.model_dump(exclude_unset=True)
    if "category_id" in updates:
        await get_category(db, owner_id, updates["category_id"])
    for field, value in updates.items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, owner_id: uuid.UUID, rule_id: uuid.UUID) -> None:
    rule = await _get_rule(db, owner_id, rule_id)
    await db.delete(rule)
    await db.commit()


async def materialize_due_expenses(db: AsyncSession, today: date | None = None) -> int:
    today = today or date.today()
    result = await db.execute(
        select(RecurringExpenseRule).where(RecurringExpenseRule.is_active.is_(True))
    )
    rules = list(result.scalars().all())

    created = 0
    for rule in rules:
        cycles = 0
        while rule.next_run <= today and cycles < _MAX_CATCHUP_CYCLES:
            db.add(
                Expense(
                    owner_id=rule.owner_id,
                    category_id=rule.category_id,
                    amount=rule.amount,
                    merchant=rule.merchant,
                    note=rule.note,
                    date=rule.next_run,
                )
            )
            rule.next_run = _advance(rule.next_run, rule.cadence)
            created += 1
            cycles += 1

    await db.commit()
    return created
