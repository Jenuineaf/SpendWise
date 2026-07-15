import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=50)


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    icon: str | None = Field(default=None, max_length=50)


class CategoryRead(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_default: bool
    created_at: datetime
