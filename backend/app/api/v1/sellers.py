from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.core.config import settings
from app.db.session import get_db
from app.models import (
    Product,
    SellerInvitation,
    Store,
    SubscriptionPlan,
    User,
)
from app.schemas.seller import (
    AdminSellerCreateRequest,
    AdminSellerCreateResponse,
    AdminSellerInvitationRegenerateRequest,
    AdminSellerInvitationRegenerateResponse,
    AdminSellerOnboardingCancelRequest,
    AdminSellerOnboardingCancelResponse,
    AdminSellerInvitationSummary,
    AdminSellerListItem,
    AdminSellerListResponse,
    AdminSellerStoreSummary,
)
from app.services.store_publication import (
    get_admin_publish_blockers,
)
from app.services.seller_listing import (
    decode_seller_cursor,
    derive_account_status,
    derive_invitation_status,
    derive_setup_status,
    encode_seller_cursor,
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


def _seller_is_pending_onboarding(
    seller: User,
) -> bool:
    return (
        seller.role == "merchant"
        and seller.password_hash is None
        and seller.is_active is False
        and seller.is_verified is False
    )


async def _lock_pending_seller(
    db: AsyncSession,
    seller_id: UUID,
) -> User:
    seller_result = await db.execute(
        select(User)
        .where(User.id == seller_id)
        .with_for_update()
    )

    seller = seller_result.scalar_one_or_none()

    if seller is None or seller.role != "merchant":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seller not found.",
        )

    if not _seller_is_pending_onboarding(seller):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This seller has already completed "
                "account setup."
            ),
        )

    return seller


async def _load_open_invitation_for_update(
    db: AsyncSession,
    seller_id: UUID,
) -> SellerInvitation | None:
    invitation_result = await db.execute(
        select(SellerInvitation)
        .where(
            SellerInvitation.user_id == seller_id,
            SellerInvitation.accepted_at.is_(None),
            SellerInvitation.revoked_at.is_(None),
        )
        .with_for_update()
    )

    return invitation_result.scalar_one_or_none()


async def _load_latest_invitation_for_update(
    db: AsyncSession,
    seller_id: UUID,
) -> SellerInvitation | None:
    invitation_result = await db.execute(
        select(SellerInvitation)
        .where(
            SellerInvitation.user_id == seller_id
        )
        .order_by(
            SellerInvitation.created_at.desc(),
            SellerInvitation.id.desc(),
        )
        .limit(1)
        .with_for_update()
    )

    return invitation_result.scalar_one_or_none()


@router.post(
    "/{seller_id}/invitation/regenerate",
    response_model=(
        AdminSellerInvitationRegenerateResponse
    ),
    status_code=status.HTTP_201_CREATED,
)
async def regenerate_seller_invitation(
    seller_id: UUID,
    payload: AdminSellerInvitationRegenerateRequest,
    current_admin: User = Depends(
        require_platform_admin
    ),
    db: AsyncSession = Depends(get_db),
) -> AdminSellerInvitationRegenerateResponse:
    try:
        seller = await _lock_pending_seller(
            db,
            seller_id,
        )

        open_invitation = (
            await _load_open_invitation_for_update(
                db,
                seller.id,
            )
        )

        expected_invitation_id = (
            payload.current_invitation_id
        )

        if expected_invitation_id is None:
            if open_invitation is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "An active invitation already exists. "
                        "Refresh and try again."
                    ),
                )
        elif (
            open_invitation is None
            or open_invitation.id
            != expected_invitation_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The invitation has already changed. "
                    "Refresh and try again."
                ),
            )

        source_invitation = open_invitation

        if source_invitation is None:
            source_invitation = (
                await _load_latest_invitation_for_update(
                    db,
                    seller.id,
                )
            )

        if source_invitation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Seller invitation not found.",
            )

        store_result = await db.execute(
            select(Store).where(
                Store.id == source_invitation.store_id,
                Store.owner_id == seller.id,
            )
        )

        store = store_result.scalar_one_or_none()

        if store is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The seller's onboarding store "
                    "is unavailable."
                ),
            )

        now = datetime.now(timezone.utc)

        if open_invitation is not None:
            open_invitation.revoked_at = now

            # Close the previous invitation before inserting
            # the next row so the partial unique index remains
            # authoritative.
            await db.flush()

        raw_token = generate_invitation_token()
        expires_at = get_invitation_expiry(now)

        new_invitation = SellerInvitation(
            user_id=seller.id,
            store_id=store.id,
            token_hash=hash_invitation_token(
                raw_token
            ),
            expires_at=expires_at,
            accepted_at=None,
            revoked_at=None,
            created_by_user_id=current_admin.id,
        )

        db.add(new_invitation)
        await db.flush()

        response = (
            AdminSellerInvitationRegenerateResponse(
                seller_id=seller.id,
                store_id=store.id,
                invitation_id=new_invitation.id,
                invitation_expires_at=expires_at,
                invitation_url=build_invitation_url(
                    raw_token
                ),
            )
        )

        await db.commit()

        return response

    except IntegrityError as exc:
        await db.rollback()

        if _integrity_sqlstate(exc) == "23505":
            constraint_name = (
                _integrity_constraint_name(exc)
            )

            if constraint_name == (
                "uq_seller_invitations_"
                "one_open_per_user"
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The invitation has already changed. "
                        "Refresh and try again."
                    ),
                ) from exc

            if constraint_name == (
                "uq_seller_invitations_token_hash"
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Unable to generate a new "
                        "invitation. Please try again."
                    ),
                ) from exc

        raise

    except Exception:
        await db.rollback()
        raise


@router.post(
    "/{seller_id}/cancel-onboarding",
    response_model=(
        AdminSellerOnboardingCancelResponse
    ),
)
async def cancel_seller_onboarding(
    seller_id: UUID,
    payload: AdminSellerOnboardingCancelRequest,
    current_admin: User = Depends(
        require_platform_admin
    ),
    db: AsyncSession = Depends(get_db),
) -> AdminSellerOnboardingCancelResponse:
    del current_admin

    try:
        seller = await _lock_pending_seller(
            db,
            seller_id,
        )

        open_invitation = (
            await _load_open_invitation_for_update(
                db,
                seller.id,
            )
        )

        if (
            open_invitation is None
            or open_invitation.id
            != payload.current_invitation_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The invitation has already changed "
                    "or onboarding is already cancelled."
                ),
            )

        now = datetime.now(timezone.utc)

        open_invitation.revoked_at = now

        # Seller account and Draft store are retained.
        # The revoked invitation prevents account setup.
        await db.commit()

        return AdminSellerOnboardingCancelResponse(
            seller_id=seller.id,
            invitation_id=open_invitation.id,
            onboarding_status="cancelled",
            revoked_at=now,
        )

    except Exception:
        await db.rollback()
        raise


@router.get(
    "",
    response_model=AdminSellerListResponse,
)
async def list_admin_sellers(
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description=(
                "Number of seller accounts to return."
            ),
        ),
    ] = 25,
    cursor: Annotated[
        str | None,
        Query(
            max_length=512,
            description=(
                "Opaque cursor from the previous page."
            ),
        ),
    ] = None,
    current_admin: User = Depends(
        require_platform_admin
    ),
    db: AsyncSession = Depends(get_db),
) -> AdminSellerListResponse:
    del current_admin

    cursor_value = (
        decode_seller_cursor(cursor)
        if cursor is not None
        else None
    )

    seller_query = select(User).where(
        User.role == "merchant"
    )

    if cursor_value is not None:
        seller_query = seller_query.where(
            or_(
                User.created_at
                < cursor_value.created_at,
                and_(
                    User.created_at
                    == cursor_value.created_at,
                    User.id
                    < cursor_value.seller_id,
                ),
            )
        )

    seller_result = await db.execute(
        seller_query
        .order_by(
            User.created_at.desc(),
            User.id.desc(),
        )
        .limit(limit + 1)
    )

    fetched_sellers = list(
        seller_result.scalars().all()
    )

    has_more = len(fetched_sellers) > limit
    sellers = fetched_sellers[:limit]

    if not sellers:
        return AdminSellerListResponse(
            items=[],
            next_cursor=None,
            has_more=False,
        )

    seller_ids = [
        seller.id
        for seller in sellers
    ]

    store_result = await db.execute(
        select(Store)
        .where(
            Store.owner_id.in_(seller_ids)
        )
        .order_by(
            Store.owner_id.asc(),
            Store.created_at.desc(),
            Store.id.desc(),
        )
    )

    stores_by_seller: dict[
        UUID,
        list[Store],
    ] = {
        seller_id: []
        for seller_id in seller_ids
    }

    all_seller_stores = list(
        store_result.scalars().all()
    )

    for store in all_seller_stores:
        stores_by_seller.setdefault(
            store.owner_id,
            [],
        ).append(store)

    store_ids = [
        store.id
        for store in all_seller_stores
    ]
    active_product_counts: dict[UUID, int] = {}

    if store_ids:
        product_count_result = await db.execute(
            select(
                Product.store_id,
                func.count(Product.id),
            )
            .where(
                Product.store_id.in_(store_ids),
                Product.is_active.is_(True),
            )
            .group_by(Product.store_id)
        )

        active_product_counts = {
            store_id: int(product_count)
            for store_id, product_count
            in product_count_result.all()
        }

    ranked_invitations = (
        select(
            SellerInvitation.id.label(
                "invitation_id"
            ),
            func.row_number()
            .over(
                partition_by=(
                    SellerInvitation.user_id
                ),
                order_by=(
                    SellerInvitation
                    .created_at.desc(),
                    SellerInvitation.id.desc(),
                ),
            )
            .label("row_number"),
        )
        .where(
            SellerInvitation.user_id.in_(
                seller_ids
            )
        )
        .subquery()
    )

    invitation_result = await db.execute(
        select(SellerInvitation)
        .join(
            ranked_invitations,
            ranked_invitations.c.invitation_id
            == SellerInvitation.id,
        )
        .where(
            ranked_invitations.c.row_number == 1
        )
    )

    latest_invitation_by_seller = {
        invitation.user_id: invitation
        for invitation
        in invitation_result.scalars().all()
    }

    now = datetime.now(timezone.utc)
    items: list[AdminSellerListItem] = []

    for seller in sellers:
        try:
            account_status = (
                derive_account_status(seller)
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Seller account state is "
                    "inconsistent."
                ),
            ) from exc

        latest_invitation = (
            latest_invitation_by_seller.get(
                seller.id
            )
        )

        invitation_status = (
            derive_invitation_status(
                latest_invitation,
                now,
            )
        )

        invitation_summary = None

        if latest_invitation is not None:
            invitation_summary = (
                AdminSellerInvitationSummary(
                    id=latest_invitation.id,
                    store_id=(
                        latest_invitation.store_id
                    ),
                    status=invitation_status,
                    expires_at=(
                        latest_invitation.expires_at
                    ),
                    accepted_at=(
                        latest_invitation.accepted_at
                    ),
                    revoked_at=(
                        latest_invitation.revoked_at
                    ),
                    created_at=(
                        latest_invitation.created_at
                    ),
                )
            )

        seller_stores = stores_by_seller.get(
            seller.id,
            [],
        )

        store_summaries = []

        for store in seller_stores:
            active_product_count = (
                active_product_counts.get(
                    store.id,
                    0,
                )
            )
            publish_blockers = (
                get_admin_publish_blockers(
                    store=store,
                    owner=seller,
                    active_product_count=(
                        active_product_count
                    ),
                    now=now,
                )
            )

            store_summaries.append(
                AdminSellerStoreSummary(
                    id=store.id,
                    name=store.name,
                    slug=store.slug,
                    publication_status=(
                        store.publication_status
                    ),
                    is_active=store.is_active,
                    is_suspended=(
                        store.is_suspended
                    ),
                    plan_name=store.plan_name,
                    subscription_status=(
                        store.subscription_status
                    ),
                    monthly_fee=store.monthly_fee,
                    trial_ends_at=(
                        store.trial_ends_at
                    ),
                    subscription_ends_at=(
                        store.subscription_ends_at
                    ),
                    last_payment_at=(
                        store.last_payment_at
                    ),
                    active_product_count=(
                        active_product_count
                    ),
                    publish_ready=(
                        not publish_blockers
                    ),
                    publish_blockers=(
                        publish_blockers
                    ),
                    created_at=store.created_at,
                    updated_at=store.updated_at,
                )
            )

        items.append(
            AdminSellerListItem(
                seller_id=seller.id,
                full_name=seller.full_name,
                email=seller.email,
                phone_number=(
                    seller.phone_number
                ),
                account_status=account_status,
                setup_status=(
                    derive_setup_status(
                        seller,
                        invitation_status,
                    )
                ),
                invitation_status=(
                    invitation_status
                ),
                latest_invitation=(
                    invitation_summary
                ),
                store_count=len(
                    store_summaries
                ),
                stores=store_summaries,
                created_at=seller.created_at,
                updated_at=seller.updated_at,
            )
        )

    next_cursor = None

    if has_more:
        final_seller = sellers[-1]

        next_cursor = encode_seller_cursor(
            final_seller.created_at,
            final_seller.id,
        )

    return AdminSellerListResponse(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )
