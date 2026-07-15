import uuid
from datetime import datetime

from pydantic import BaseModel


class BudgetAlertRead(BaseModel):
    id: uuid.UUID
    budget_id: uuid.UUID
    category_name: str
    threshold: int
    triggered_at: datetime
