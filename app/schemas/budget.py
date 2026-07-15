import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BudgetBase(BaseModel):
    category_id: uuid.UUID
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class BudgetCreate(BudgetBase):
    pass


class BudgetUpdate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    year: int
    month: int
    amount: Decimal
    spent: Decimal
    remaining: Decimal
    percent_used: float
    created_at: datetime
    updated_at: datetime
