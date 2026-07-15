import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SavingsGoalBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    deadline: date


class SavingsGoalCreate(SavingsGoalBase):
    pass


class SavingsGoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    target_amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    deadline: date | None = None


class SavingsGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    target_amount: Decimal
    deadline: date
    created_at: datetime
    monthly_income: Decimal | None
    avg_monthly_expense: Decimal
    estimated_monthly_savings: Decimal
    months_remaining: int
    projected_savings: Decimal
    percent_of_target: float
    on_track: bool
