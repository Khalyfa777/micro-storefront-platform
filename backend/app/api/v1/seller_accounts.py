from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.db.session import get_db
from app.models import (
    Product,
    SellerAccountEvent,
    SellerInvitation,
    Store,
    SubscriptionPayment,
    User,
)
from app.schemas.seller import (
    AdminSellerAccountActionRequest,
    AdminSellerAccountActionResponse,
    AdminSellerAccountEventSummary,
    AdminSellerDetailResponse,
    AdminSellerInvitationSummary,
    AdminSellerStoreSummary,
    AdminSellerSubscriptionPaymentSummary,
)
from app.services.store_publication import (
    get_admin_publish_blockers,
)
from app.services.seller_listing import (
    derive_account_status,
    derive_invitation_status,
    derive_setup_status,
)


router = APIRouter(
    prefix="/admin/sellers",
    tags=["admin-seller-accounts"],
)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _seller_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Seller not found.",
    )


def _account_state_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Seller account state is inconsistent.",
    )


def _derive_account_status_or_conflict(
    seller: User,
) -> Literal[
    "invited",
    "active",
    "suspended",
]:
    try:
        return derive_account_status(seller)
    except ValueError as exc:
        raise _account_state_conflict() from exc


async def _load_merchant(
    db: AsyncSession,
    seller_id: UUID,
    *,
    lock: bool = False,
) -> User:
    query = select(User).where(
        User.id == seller_id,
        User.role == "merchant",
    )

    if lock:
        query = query.with_for_update()

    result = await db.execute(query)
    seller = result.scalar_one_or_none()

    if seller is None:
        raise _seller_not_found()

    return seller


def _store_summary(
    store: Store,
    *,
    owner: User,
    active_product_count: int,
    now: datetime,
) -> AdminSellerStoreSummary:
    publish_blockers = get_admin_publish_blockers(
        store=store,
        owner=owner,
        active_product_count=active_product_count,
        now=now,
    )

    return AdminSellerStoreSummary(
        id=store.id,
        name=store.name,
        slug=store.slug,
        publication_status=(
            store.publication_status
        ),
        is_active=store.is_active,
        is_suspended=store.is_suspended,
        plan_name=store.plan_name,
        subscription_status=(
            store.subscription_status
        ),
        monthly_fee=store.monthly_fee,
        active_product_count=active_product_count,
        publish_ready=not publish_blockers,
        publish_blockers=publish_blockers,
        trial_ends_at=store.trial_ends_at,
        subscription_ends_at=(
            store.subscription_ends_at
        ),
        last_payment_at=store.last_payment_at,
        created_at=store.created_at,
        updated_at=store.updated_at,
    )


@router.get(
    "/{seller_id}",
    response_model=AdminSellerDetailResponse,
)
async def get_admin_seller_detail(
    seller_id: UUID,
    current_admin: User = Depends(
        require_platform_admin
    ),
    db: AsyncSession = Depends(get_db),
) -> AdminSellerDetailResponse:
    del current_admin

    seller = await _load_merchant(
        db,
        seller_id,
    )

    account_status = (
        _derive_account_status_or_conflict(
            seller
        )
    )

    store_result = await db.execute(
        select(Store)
        .where(Store.owner_id == seller.id)
        .order_by(
            Store.created_at.desc(),
            Store.id.desc(),
        )
    )

    stores = list(
        store_result.scalars().all()
    )

    invitation_result = await db.execute(
        select(SellerInvitation)
        .where(
            SellerInvitation.user_id
            == seller.id
        )
        .order_by(
            SellerInvitation.created_at.desc(),
            SellerInvitation.id.desc(),
        )
    )

    invitations = list(
        invitation_result.scalars().all()
    )

    now = datetime.now(timezone.utc)

    invitation_summaries = [
        AdminSellerInvitationSummary(
            id=invitation.id,
            store_id=invitation.store_id,
            status=derive_invitation_status(
                invitation,
                now,
            ),
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            revoked_at=invitation.revoked_at,
            created_at=invitation.created_at,
        )
        for invitation in invitations
    ]

    latest_invitation = (
        invitation_summaries[0]
        if invitation_summaries
        else None
    )

    invitation_status = (
        latest_invitation.status
        if latest_invitation is not None
        else "none"
    )

    event_result = await db.execute(
        select(
            SellerAccountEvent,
            User.email,
        )
        .outerjoin(
            User,
            User.id
            == SellerAccountEvent.actor_user_id,
        )
        .where(
            SellerAccountEvent.seller_id
            == seller.id
        )
        .order_by(
            SellerAccountEvent.created_at.desc(),
            SellerAccountEvent.id.desc(),
        )
    )

    account_events = [
        AdminSellerAccountEventSummary(
            id=event.id,
            action=event.action,
            previous_account_status=(
                event.previous_account_status
            ),
            new_account_status=(
                event.new_account_status
            ),
            reason=event.reason,
            actor_user_id=event.actor_user_id,
            actor_email=actor_email,
            created_at=event.created_at,
        )
        for event, actor_email
        in event_result.all()
    ]

    store_ids = [store.id for store in stores]
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

    store_summaries = [
        _store_summary(
            store,
            owner=seller,
            active_product_count=(
                active_product_counts.get(
                    store.id,
                    0,
                )
            ),
            now=now,
        )
        for store in stores
    ]

    subscription_payments = []

    if store_ids:
        payment_result = await db.execute(
            select(
                SubscriptionPayment,
                User.email,
            )
            .outerjoin(
                User,
                User.id
                == SubscriptionPayment.approved_by_user_id,
            )
            .where(
                SubscriptionPayment.store_id.in_(
                    store_ids
                )
            )
            .order_by(
                SubscriptionPayment.paid_at.desc(),
                SubscriptionPayment.id.desc(),
            )
            .limit(50)
        )

        subscription_payments = [
            AdminSellerSubscriptionPaymentSummary(
                id=payment.id,
                store_id=payment.store_id,
                plan_name=payment.plan_name,
                amount=payment.amount,
                currency=payment.currency,
                payment_method=payment.payment_method,
                payment_reference=(
                    payment.payment_reference
                ),
                note=payment.note,
                covered_days=payment.covered_days,
                approved_by_email=approved_by_email,
                paid_at=payment.paid_at,
                created_at=payment.created_at,
            )
            for payment, approved_by_email
            in payment_result.all()
        ]

    return AdminSellerDetailResponse(
        seller_id=seller.id,
        full_name=seller.full_name,
        email=seller.email,
        phone_number=seller.phone_number,
        account_status=account_status,
        setup_status=derive_setup_status(
            seller,
            invitation_status,
        ),
        invitation_status=invitation_status,
        is_active=seller.is_active,
        is_verified=seller.is_verified,
        has_password=(
            seller.password_hash is not None
        ),
        latest_invitation=latest_invitation,
        invitation_count=len(
            invitation_summaries
        ),
        invitations=invitation_summaries,
        store_count=len(store_summaries),
        stores=store_summaries,
        account_event_count=len(
            account_events
        ),
        account_events=account_events,
        subscription_payment_count=len(
            subscription_payments
        ),
        subscription_payments=(
            subscription_payments
        ),
        created_at=seller.created_at,
        updated_at=seller.updated_at,
    )


async def _transition_seller_account(
    *,
    seller_id: UUID,
    payload: AdminSellerAccountActionRequest,
    current_admin: User,
    db: AsyncSession,
    action: Literal[
        "suspend",
        "reactivate",
    ],
) -> AdminSellerAccountActionResponse:
    try:
        seller = await _load_merchant(
            db,
            seller_id,
            lock=True,
        )

        current_status = (
            _derive_account_status_or_conflict(
                seller
            )
        )

        if (
            _to_utc(seller.updated_at)
            != _to_utc(
                payload.expected_updated_at
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Seller account changed. "
                    "Refresh and try again."
                ),
            )

        if current_status == "invited":
            if action == "suspend":
                detail = (
                    "Invited sellers must use "
                    "onboarding cancellation instead."
                )
            else:
                detail = (
                    "Seller onboarding has not "
                    "been completed."
                )

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            )

        if seller.password_hash is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Seller account setup is "
                    "incomplete."
                ),
            )

        if action == "suspend":
            if current_status == "suspended":
                raise HTTPException(
                    status_code=(
                        status.HTTP_409_CONFLICT
                    ),
                    detail=(
                        "Seller account is already "
                        "suspended."
                    ),
                )

            new_status = "suspended"
            new_is_active = False

        else:
            if current_status == "active":
                raise HTTPException(
                    status_code=(
                        status.HTTP_409_CONFLICT
                    ),
                    detail=(
                        "Seller account is already "
                        "active."
                    ),
                )

            new_status = "active"
            new_is_active = True

        changed_at = datetime.now(timezone.utc)

        event = SellerAccountEvent(
            seller_id=seller.id,
            actor_user_id=current_admin.id,
            action=action,
            previous_account_status=(
                current_status
            ),
            new_account_status=new_status,
            reason=payload.reason,
        )

        seller.is_active = new_is_active

        # Verification, password, stores,
        # publication and subscriptions are
        # intentionally untouched.
        seller.updated_at = changed_at

        db.add(event)
        await db.flush()

        response = (
            AdminSellerAccountActionResponse(
                seller_id=seller.id,
                event_id=event.id,
                account_status=new_status,
                is_active=seller.is_active,
                is_verified=seller.is_verified,
                updated_at=changed_at,
            )
        )

        await db.commit()

        return response

    except Exception:
        await db.rollback()
        raise


@router.post(
    "/{seller_id}/suspend",
    response_model=(
        AdminSellerAccountActionResponse
    ),
)
async def suspend_seller_account(
    seller_id: UUID,
    payload: AdminSellerAccountActionRequest,
    current_admin: User = Depends(
        require_platform_admin
    ),
    db: AsyncSession = Depends(get_db),
) -> AdminSellerAccountActionResponse:
    return await _transition_seller_account(
        seller_id=seller_id,
        payload=payload,
        current_admin=current_admin,
        db=db,
        action="suspend",
    )


@router.post(
    "/{seller_id}/reactivate",
    response_model=(
        AdminSellerAccountActionResponse
    ),
)
async def reactivate_seller_account(
    seller_id: UUID,
    payload: AdminSellerAccountActionRequest,
    current_admin: User = Depends(
        require_platform_admin
    ),
    db: AsyncSession = Depends(get_db),
) -> AdminSellerAccountActionResponse:
    return await _transition_seller_account(
        seller_id=seller_id,
        payload=payload,
        current_admin=current_admin,
        db=db,
        action="reactivate",
    )
