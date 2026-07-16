from uuid import UUID

from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models import Store, User


bearer = HTTPBearer(auto_error=False)


def _raise_invalid_token() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token.",
    )


async def get_current_user(
    credentials: (
        HTTPAuthorizationCredentials
        | None
    ) = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    try:
        payload = decode_token(
            credentials.credentials
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        ) from exc

    if payload.get("type") != "access":
        _raise_invalid_token()

    token_version = payload.get("ver")

    if (
        isinstance(token_version, bool)
        or not isinstance(
            token_version,
            int,
        )
        or token_version < 0
    ):
        _raise_invalid_token()

    subject = payload.get("sub")

    try:
        user_id = UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
        ) from exc

    result = await db.execute(
        select(User).where(
            User.id == user_id,
        )
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    if user.token_version != token_version:
        _raise_invalid_token()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not active.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Account verification is required."
            ),
        )

    return user


async def require_store_owner(
    store_id: str,
    user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> Store:
    result = await db.execute(
        select(Store).where(
            Store.id == store_id,
            Store.owner_id == user.id,
        )
    )

    store = result.scalar_one_or_none()

    if not store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found.",
        )

    return store


async def require_platform_admin(
    user: User = Depends(
        get_current_user
    ),
) -> User:
    allowed_roles = {
        "admin",
        "platform_admin",
        "super_admin",
    }

    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Platform admin access required."
            ),
        )

    return user
