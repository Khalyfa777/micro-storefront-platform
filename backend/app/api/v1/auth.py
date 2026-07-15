from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.concurrency import (
    run_in_threadpool,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth_rate_limit import (
    clear_login_rate_limit,
    enforce_login_rate_limit,
)


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


# Valid bcrypt hash used only to equalize password
# verification work when no account password exists.
# It is not associated with a real account.
DUMMY_LOGIN_PASSWORD_HASH = (
    "$2b$12$C6UzMDM.H6dfI/f/IKcEe."
    "5BE4g6Mwdt4PGMTgpT2q47R4F8AT0sK"
)


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_full_name(value: str) -> str:
    return " ".join(value.split())


def _integrity_constraint_name(
    exc: IntegrityError,
) -> str | None:
    diagnostic = getattr(
        exc.orig,
        "diag",
        None,
    )

    if diagnostic is None:
        return None

    return getattr(
        diagnostic,
        "constraint_name",
        None,
    )


def _integrity_sqlstate(
    exc: IntegrityError,
) -> str | None:
    return (
        getattr(
            exc.orig,
            "sqlstate",
            None,
        )
        or getattr(
            exc.orig,
            "pgcode",
            None,
        )
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
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Public registration is disabled."
            ),
        )

    normalized_email = _normalize_email(
        str(payload.email)
    )
    normalized_name = _normalize_full_name(
        payload.full_name
    )

    exists = await db.execute(
        select(User.id).where(
            User.email == normalized_email,
        )
    )

    if exists.scalar_one_or_none():
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail="Email already registered.",
        )

    password_hash = await run_in_threadpool(
        hash_password,
        payload.password,
    )

    user = User(
        email=normalized_email,
        full_name=normalized_name,
        password_hash=password_hash,
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
            _integrity_sqlstate(exc)
            == "23505"
            and _integrity_constraint_name(
                exc
            )
            == "ix_users_email"
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Email already registered."
                ),
            ) from exc

        raise

    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(
            str(user.id),
            user.role,
            user.token_version,
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
    normalized_email = _normalize_email(
        str(payload.email)
    )

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

    password_hash = (
        user.password_hash
        if user and user.password_hash
        else DUMMY_LOGIN_PASSWORD_HASH
    )

    password_matches = (
        await run_in_threadpool(
            verify_password,
            payload.password,
            password_hash,
        )
    )

    credentials_are_valid = bool(
        user
        and user.password_hash
        and password_matches
    )

    if not credentials_are_valid:
        raise HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid email or password."
            ),
        )

    if not user.is_active:
        if user.is_verified:
            detail = (
                "This account has been "
                "suspended."
            )
        else:
            detail = (
                "Account setup is incomplete."
            )

        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=detail,
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=(
                "Account verification is "
                "required."
            ),
        )

    await clear_login_rate_limit(
        request,
        normalized_email,
    )

    return TokenResponse(
        access_token=create_access_token(
            str(user.id),
            user.role,
            user.token_version,
        )
    )


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
) -> ChangePasswordResponse:
    current_password_hash = (
        current_user.password_hash
    )

    if current_password_hash is None:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "Account password setup is "
                "incomplete."
            ),
        )

    current_password_matches = (
        await run_in_threadpool(
            verify_password,
            payload.current_password,
            current_password_hash,
        )
    )

    if not current_password_matches:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Current password is incorrect."
            ),
        )

    if (
        payload.new_password
        == payload.current_password
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "New password must be different "
                "from the current password."
            ),
        )

    expected_token_version = (
        current_user.token_version
    )

    new_password_hash = (
        await run_in_threadpool(
            hash_password,
            payload.new_password,
        )
    )

    try:
        locked_result = await db.execute(
            select(User)
            .where(
                User.id == current_user.id,
            )
            .with_for_update()
            .execution_options(
                populate_existing=True,
            )
        )

        locked_user = (
            locked_result.scalar_one_or_none()
        )

        if locked_user is None:
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail="User not found.",
            )

        if (
            locked_user.password_hash
            != current_password_hash
            or locked_user.token_version
            != expected_token_version
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "Account credentials changed. "
                    "Sign in again and retry."
                ),
            )

        locked_user.password_hash = (
            new_password_hash
        )
        locked_user.token_version = (
            expected_token_version + 1
        )

        await db.commit()

    except HTTPException:
        await db.rollback()
        raise

    except Exception:
        await db.rollback()
        raise

    return ChangePasswordResponse(
        detail=(
            "Password updated. Sign in again "
            "with your new password."
        )
    )
