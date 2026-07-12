from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.core.config import settings
from app.db.session import get_db
from app.models import (
    SellerInvitation,
    Store,
    SubscriptionPlan,
    User,
)
from app.schemas.seller import (
    AdminSellerCreateRequest,
    AdminSellerCreateResponse,
)
from app.services.seller_invitation import (
    build_invitation_url,
    generate_invitation_token,
    get_invitation_expiry,
    hash_invitation_token,
)


router = APIRouter(
    prefix="/admin/sellers",
    tags=["admin-sellers"],
)


def _integrity_constraint_name(
    exc: IntegrityError,
) -> str | None:
    candidates = [
        exc.orig,
        getattr(exc.orig, "__cause__", None),
        getattr(exc.orig, "__context__", None),
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        direct_name = getattr(
            candidate,
            "constraint_name",
            None,
        )

        if direct_name:
            return str(direct_name)

        diagnostic = getattr(candidate, "diag", None)

        diagnostic_name = getattr(
            diagnostic,
            "constraint_name",
            None,
        )

        if diagnostic_name:
            return str(diagnostic_name)

    return None


def _integrity_sqlstate(
    exc: IntegrityError,
) -> str | None:
    candidates = [
        exc.orig,
        getattr(exc.orig, "__cause__", None),
        getattr(exc.orig, "__context__", None),
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        value = (
            getattr(candidate, "sqlstate", None)
            or getattr(candidate, "pgcode", None)
        )

        if value:
            return str(value)

    return None


def _duplicate_error(
    constraint_name: str | None,
) -> HTTPException:
    if constraint_name == "ix_users_email":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A seller with this email already exists.",
        )

    if constraint_name == "ix_stores_slug":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Store slug is already taken.",
        )

    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Unable to create the seller because "
            "a unique value already exists."
        ),
    )


@router.post(
    "",
    response_model=AdminSellerCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_seller(
    payload: AdminSellerCreateRequest,
    current_admin: User = Depends(
        require_platform_admin
    ),
    db: AsyncSession = Depends(get_db),
) -> AdminSellerCreateResponse:
    normalized_email = str(payload.email).strip().lower()

    plan_result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.name == payload.plan_name,
            SubscriptionPlan.is_active.is_(True),
        )
    )

    plan = plan_result.scalar_one_or_none()

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected subscription plan is unavailable.",
        )

    existing_user_result = await db.execute(
        select(User.id).where(
            User.email == normalized_email,
        )
    )

    if existing_user_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A seller with this email already exists.",
        )

    existing_store_result = await db.execute(
        select(Store.id).where(
            Store.slug == payload.store_slug,
        )
    )

    if existing_store_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Store slug is already taken.",
        )

    now = datetime.now(timezone.utc)
    trial_ends_at = now + timedelta(
        days=settings.TRIAL_DAYS
    )

    raw_invitation_token = generate_invitation_token()
    invitation_expires_at = get_invitation_expiry(now)

    seller = User(
        email=normalized_email,
        password_hash=None,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
        role="merchant",
        is_active=False,
        is_verified=False,
    )

    try:
        db.add(seller)
        await db.flush()

        store = Store(
            owner_id=seller.id,
            slug=payload.store_slug,
            name=payload.store_name,
            social_links={},
            theme="default",
            is_active=True,
            is_suspended=False,
            publication_status="draft",
            plan_name=plan.name,
            subscription_status="trial",
            trial_ends_at=trial_ends_at,
            subscription_ends_at=None,
            last_payment_at=None,
            monthly_fee=Decimal("0.00"),
        )

        db.add(store)
        await db.flush()

        invitation = SellerInvitation(
            user_id=seller.id,
            store_id=store.id,
            token_hash=hash_invitation_token(
                raw_invitation_token
            ),
            expires_at=invitation_expires_at,
            accepted_at=None,
            revoked_at=None,
            created_by_user_id=current_admin.id,
        )

        db.add(invitation)
        await db.flush()

        response = AdminSellerCreateResponse(
            seller_id=seller.id,
            store_id=store.id,
            invitation_id=invitation.id,
            full_name=seller.full_name,
            email=seller.email,
            phone_number=seller.phone_number,
            store_name=store.name,
            store_slug=store.slug,
            account_status="invited",
            publication_status="draft",
            plan_name=store.plan_name,
            subscription_status="trial",
            monthly_fee=Decimal("0.00"),
            trial_ends_at=trial_ends_at,
            invitation_expires_at=invitation_expires_at,
            invitation_url=build_invitation_url(
                raw_invitation_token
            ),
        )

        await db.commit()

        return response

    except IntegrityError as exc:
        await db.rollback()

        if _integrity_sqlstate(exc) == "23505":
            raise _duplicate_error(
                _integrity_constraint_name(exc)
            ) from exc

        raise

    except Exception:
        await db.rollback()
        raise
