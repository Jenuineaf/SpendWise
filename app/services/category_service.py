import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.category import Category
from app.models.expense import Expense
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryUpdate

DEFAULT_CATEGORIES = [
    ("Food & Dining", "utensils"),
    ("Groceries", "shopping-cart"),
    ("Transport", "car"),
    ("Shopping", "bag"),
    ("Bills & Utilities", "receipt"),
    ("Entertainment", "film"),
    ("Health", "heart-pulse"),
    ("Rent", "home"),
    ("Travel", "plane"),
    ("Other", "dots-horizontal"),
]


async def seed_default_categories(db: AsyncSession, user: User) -> None:
    for name, icon in DEFAULT_CATEGORIES:
        db.add(Category(owner_id=user.id, name=name, icon=icon, is_default=True))
    await db.commit()


async def list_categories(db: AsyncSession, owner_id: uuid.UUID) -> list[Category]:
    result = await db.execute(
        select(Category).where(Category.owner_id == owner_id).order_by(Category.name)
    )
    return list(result.scalars().all())


async def get_category(db: AsyncSession, owner_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    result = await db.execute(
        select(Category).where(Category.id == category_id, Category.owner_id == owner_id)
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundError("Category not found")
    return category


async def create_category(db: AsyncSession, owner_id: uuid.UUID, data: CategoryCreate) -> Category:
    existing = await db.execute(
        select(Category).where(Category.owner_id == owner_id, Category.name == data.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("Category with this name already exists")
    category = Category(owner_id=owner_id, name=data.name, icon=data.icon)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


async def update_category(
    db: AsyncSession, owner_id: uuid.UUID, category_id: uuid.UUID, data: CategoryUpdate
) -> Category:
    category = await get_category(db, owner_id, category_id)
    if data.name is not None:
        category.name = data.name
    if data.icon is not None:
        category.icon = data.icon
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, owner_id: uuid.UUID, category_id: uuid.UUID) -> None:
    category = await get_category(db, owner_id, category_id)
    in_use = await db.execute(select(Expense.id).where(Expense.category_id == category_id).limit(1))
    if in_use.scalar_one_or_none() is not None:
        raise ConflictError("Cannot delete a category that has expenses; reassign them first")
    await db.delete(category)
    await db.commit()
