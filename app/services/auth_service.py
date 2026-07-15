import uuid

from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.category_service import seed_default_categories


async def register_user(db: AsyncSession, data: UserCreate) -> User:
    normalized_email = data.email.strip().lower()
    existing = await db.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("Email already registered")

    user = User(
        email=normalized_email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await seed_default_categories(db, user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    normalized_email = email.strip().lower()
    result = await db.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Incorrect email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")
    return user


def issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(str(user.id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
    }


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> dict:
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid token type")
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired refresh token") from exc

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError()
    return issue_tokens(user)


async def update_profile(db: AsyncSession, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user
