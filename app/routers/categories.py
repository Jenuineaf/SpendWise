import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DBSession
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRead])
async def list_categories(current_user: CurrentUser, db: DBSession):
    return await category_service.list_categories(db, current_user.id)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryCreate, current_user: CurrentUser, db: DBSession):
    return await category_service.create_category(db, current_user.id, data)


@router.patch("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: uuid.UUID, data: CategoryUpdate, current_user: CurrentUser, db: DBSession
):
    return await category_service.update_category(db, current_user.id, category_id, data)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await category_service.delete_category(db, current_user.id, category_id)
