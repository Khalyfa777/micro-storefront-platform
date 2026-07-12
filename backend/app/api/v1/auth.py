from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_rate_limit import (
    clear_login_rate_limit,
    enforce_login_rate_limit,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_full_name(value: str) -> str:
    return " ".join(value.split())


def _integrity_constraint_name(exc: IntegrityError) -> str | None:
    diagnostic = getattr(exc.orig, "diag", None)

    if diagnostic is None:
        return None

    return getattr(diagnostic, "constraint_name", None)


def _integrity_sqlstate(exc: IntegrityError) -> str | None:
    return (
        getattr(exc.orig, "sqlstate", None)
        or getattr(exc.orig, "pgcode", None)
    )


@router.post(
    "/register",
    response_model=TokenResponse,
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    if not settings.PUBLIC_REGISTRATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled.",
        )

    normalized_email = _normalize_email(str(payload.email))
    normalized_name = _normalize_full_name(payload.full_name)

    exists = await db.execute(
        select(User.id).where(
            User.email == normalized_email,
        )
    )

    if exists.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    user = User(
        email=normalized_email,
        full_name=normalized_name,
        password_hash=hash_password(payload.password),
        role="merchant",
        is_active=True,
        is_verified=True,
    )

    db.add(user)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()

        if (
            _integrity_sqlstate(exc) == "23505"
            and _integrity_constraint_name(exc)
            == "ix_users_email"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered.",
            ) from exc

        raise

    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(
            str(user.id),
            user.role,
        )
    )


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    normalized_email = _normalize_email(str(payload.email))

    await enforce_login_rate_limit(
        request,
        normalized_email,
    )

    result = await db.execute(
        select(User).where(
            User.email == normalized_email,
        )
    )

    user = result.scalar_one_or_none()

    credentials_are_valid = bool(
        user
        and user.password_hash
        and verify_password(
            payload.password,
            user.password_hash,
        )
    )

    if not credentials_are_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        if user.is_verified:
            detail = "This account has been suspended."
        else:
            detail = "Account setup is incomplete."

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account verification is required.",
        )

    await clear_login_rate_limit(
        request,
        normalized_email,
    )

    return TokenResponse(
        access_token=create_access_token(
            str(user.id),
            user.role,
        )
    )
