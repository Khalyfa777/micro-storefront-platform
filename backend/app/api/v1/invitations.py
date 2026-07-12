from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import get_db
from app.models import SellerInvitation, Store, User
from app.schemas.seller import (
    SellerInvitationAcceptRequest,
    SellerInvitationAcceptResponse,
    SellerInvitationTokenRequest,
    SellerInvitationValidationResponse,
)
from app.services.seller_invitation import (
    hash_invitation_token,
)
from app.services.seller_invitation_rate_limit import (
    enforce_seller_invitation_rate_limit,
)


router = APIRouter(
    prefix="/seller-invitations",
    tags=["seller-invitations"],
)


def _to_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _raise_if_invitation_unusable(
    invitation: SellerInvitation,
    now: datetime,
) -> None:
    if invitation.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invitation has already been used.",
        )

    if invitation.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invitation is no longer valid.",
        )

    if _to_aware(invitation.expires_at) <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invitation has expired.",
        )


def _seller_is_pending_onboarding(
    seller: User,
) -> bool:
    return (
        seller.password_hash is None
        and seller.is_active is False
        and seller.is_verified is False
    )


def _invitation_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Invitation not found.",
    )


@router.post(
    "/validate",
    response_model=SellerInvitationValidationResponse,
)
async def validate_seller_invitation(
    request: Request,
    payload: SellerInvitationTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> SellerInvitationValidationResponse:
    await enforce_seller_invitation_rate_limit(
        request,
        "validate",
    )

    token_hash = hash_invitation_token(payload.token)

    invitation_result = await db.execute(
        select(SellerInvitation).where(
            SellerInvitation.token_hash == token_hash
        )
    )

    invitation = invitation_result.scalar_one_or_none()

    if invitation is None:
        raise _invitation_not_found()

    now = datetime.now(timezone.utc)

    _raise_if_invitation_unusable(
        invitation,
        now,
    )

    seller_result = await db.execute(
        select(User).where(
            User.id == invitation.user_id
        )
    )

    seller = seller_result.scalar_one_or_none()

    store_result = await db.execute(
        select(Store).where(
            Store.id == invitation.store_id,
            Store.owner_id == invitation.user_id,
        )
    )

    store = store_result.scalar_one_or_none()

    if seller is None or store is None:
        raise _invitation_not_found()

    if not _seller_is_pending_onboarding(seller):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account setup is no longer available.",
        )

    return SellerInvitationValidationResponse(
        invitation_id=invitation.id,
        seller_id=seller.id,
        store_id=store.id,
        full_name=seller.full_name,
        email=seller.email,
        store_name=store.name,
        store_slug=store.slug,
        publication_status="draft",
        expires_at=invitation.expires_at,
    )


@router.post(
    "/accept",
    response_model=SellerInvitationAcceptResponse,
)
async def accept_seller_invitation(
    request: Request,
    payload: SellerInvitationAcceptRequest,
    db: AsyncSession = Depends(get_db),
) -> SellerInvitationAcceptResponse:
    await enforce_seller_invitation_rate_limit(
        request,
        "accept",
    )

    token_hash = hash_invitation_token(payload.token)

    candidate_result = await db.execute(
        select(
            SellerInvitation.id,
            SellerInvitation.user_id,
        ).where(
            SellerInvitation.token_hash == token_hash
        )
    )

    candidate = candidate_result.one_or_none()

    if candidate is None:
        raise _invitation_not_found()

    invitation_id, seller_id = candidate

    # Hash outside the database row locks.
    new_password_hash = await run_in_threadpool(
        hash_password,
        payload.password,
    )

    try:
        # All invitation mutations lock the seller first,
        # then the invitation. This consistent ordering avoids
        # deadlocks with regeneration and cancellation.
        seller_result = await db.execute(
            select(User)
            .where(User.id == seller_id)
            .with_for_update()
        )

        seller = seller_result.scalar_one_or_none()

        if seller is None:
            raise _invitation_not_found()

        invitation_result = await db.execute(
            select(SellerInvitation)
            .where(
                SellerInvitation.id == invitation_id,
                SellerInvitation.token_hash == token_hash,
            )
            .with_for_update()
        )

        invitation = (
            invitation_result.scalar_one_or_none()
        )

        if invitation is None:
            raise _invitation_not_found()

        now = datetime.now(timezone.utc)

        _raise_if_invitation_unusable(
            invitation,
            now,
        )

        if not _seller_is_pending_onboarding(seller):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Account setup is no longer available."
                ),
            )

        store_result = await db.execute(
            select(Store).where(
                Store.id == invitation.store_id,
                Store.owner_id == seller.id,
            )
        )

        store = store_result.scalar_one_or_none()

        if store is None:
            raise _invitation_not_found()

        seller.password_hash = new_password_hash
        seller.is_active = True
        seller.is_verified = True

        invitation.accepted_at = now

        # Store publication is intentionally unchanged.
        # It remains Draft after account activation.
        await db.commit()

        return SellerInvitationAcceptResponse(
            seller_id=seller.id,
            store_id=store.id,
            account_status="active",
            publication_status="draft",
            accepted_at=now,
        )

    except Exception:
        await db.rollback()
        raise
