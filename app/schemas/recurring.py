import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.recurring import Cadence


class RecurringRuleBase(BaseModel):
    category_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    merchant: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    cadence: Cadence
    next_run: date


class RecurringRuleCreate(RecurringRuleBase):
    pass


class RecurringRuleUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    category_id: uuid.UUID | None = None
    merchant: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    cadence: Cadence | None = None
    next_run: date | None = None
    is_active: bool | None = None


class RecurringRuleRead(RecurringRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
