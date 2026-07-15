import uuid
from decimal import Decimal

from pydantic import BaseModel


class MonthlyTrendPoint(BaseModel):
    year: int
    month: int
    total: Decimal


class CategoryBreakdownItem(BaseModel):
    category_id: uuid.UUID
    category_name: str
    total: Decimal
    percent: float


class TopMerchantItem(BaseModel):
    merchant: str
    total: Decimal
    count: int


class DailySpendPoint(BaseModel):
    day: int
    total: Decimal
