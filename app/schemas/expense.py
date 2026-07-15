import uuid
from datetime import date as date_
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ExpenseBase(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    category_id: uuid.UUID
    merchant: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    date: date_


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    category_id: uuid.UUID | None = None
    merchant: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    date: date_ | None = None


class ExpenseRead(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class PaginatedExpenses(BaseModel):
    items: list[ExpenseRead]
    total: int
    page: int
    page_size: int
    pages: int
