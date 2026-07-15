from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import CurrentUser, DBSession
from app.schemas.auth import Token, TokenRefreshRequest
from app.schemas.user import UserCreate, UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate, db: DBSession):
    return await auth_service.register_user(db, data)


@router.post("/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBSession):
    user = await auth_service.authenticate_user(db, form_data.username, form_data.password)
    return auth_service.issue_tokens(user)


@router.post("/refresh", response_model=Token)
async def refresh(data: TokenRefreshRequest, db: DBSession):
    return await auth_service.refresh_access_token(db, data.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(current_user: CurrentUser):
    return current_user
