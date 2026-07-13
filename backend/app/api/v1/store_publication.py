import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.db.session import get_db
from app.models import (
    Product,
    Store,
    StorePublicationEvent,
    User,
)
from app.schemas.store import StoreResponse
from app.services.store_publication import (
    build_publication_readiness_snapshot,
    get_admin_publish_blockers,
    normalized_publication_status,
    timestamps_match,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/stores",
    tags=["admin-store-publication"],
)


PLATFORM_ADMIN_ROLES = {
    "admin",
    "platform_admin",
    "super_admin",
}


class AdminStorePublicationRequest(BaseModel):
    expected_updated_at: datetime
    reason: str | None = Field(
        default=None,
        max_length=500,
    )


def ensure_platform_admin_actor(
    current_admin: User,
) -> None:
    if current_admin.role not in PLATFORM_ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )


def store_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Store not found.",
    )


async def load_store_for_update(
    db: AsyncSession,
    store_id: UUID,
) -> Store:
    result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .with_for_update()
    )

    store = result.scalar_one_or_none()

    if store is None:
        raise store_not_found()

    return store


async def transition_store_publication(
    *,
    store_id: UUID,
    payload: AdminStorePublicationRequest,
    current_admin: User,
    db: AsyncSession,
    target_status: Literal[
        "draft",
        "published",
    ],
) -> Store:
    ensure_platform_admin_actor(current_admin)

    store = await load_store_for_update(
        db,
        store_id,
    )

    if not timestamps_match(
        store.updated_at,
        payload.expected_updated_at,
    ):
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Store changed. Refresh and "
                "try again."
            ),
        )

    previous_status = (
        normalized_publication_status(store)
    )

    if previous_status == target_status:
        await db.commit()
        return store

    owner_result = await db.execute(
        select(User).where(
            User.id == store.owner_id,
        )
    )

    owner = owner_result.scalar_one_or_none()

    product_count_result = await db.execute(
        select(
            func.count(Product.id)
        ).where(
            Product.store_id == store.id,
            Product.is_active.is_(True),
        )
    )

    active_product_count = (
        product_count_result.scalar_one()
    )

    changed_at = datetime.now(
        timezone.utc,
    )

    blockers = get_admin_publish_blockers(
        store=store,
        owner=owner,
        active_product_count=(
            active_product_count
        ),
        now=changed_at,
    )

    readiness_snapshot = (
        build_publication_readiness_snapshot(
            store=store,
            owner=owner,
            active_product_count=(
                active_product_count
            ),
            blockers=blockers,
            evaluated_at=changed_at,
        )
    )

    if (
        target_status == "published"
        and blockers
    ):
        await db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Store cannot be published: "
                + " ".join(blockers)
            ),
        )

    reason = (
        payload.reason.strip()
        if payload.reason
        else None
    )

    if reason == "":
        reason = None

    store.publication_status = target_status
    store.updated_at = changed_at

    event = StorePublicationEvent(
        store_id=store.id,
        actor_user_id=current_admin.id,
        actor_role=current_admin.role,
        action=(
            "publish"
            if target_status == "published"
            else "unpublish"
        ),
        previous_publication_status=(
            previous_status
        ),
        new_publication_status=target_status,
        reason=reason,
        readiness_snapshot=readiness_snapshot,
        created_at=changed_at,
    )

    db.add(event)

    try:
        await db.flush()
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    logger.info(
        (
            "Admin %s changed store %s "
            "publication from %s to %s."
        ),
        current_admin.id,
        store.id,
        previous_status,
        target_status,
    )

    return store


@router.post(
    "/{store_id}/publish",
    response_model=StoreResponse,
)
async def publish_store(
    store_id: UUID,
    payload: AdminStorePublicationRequest,
    current_admin: User = Depends(
        require_platform_admin
    ),
    db: AsyncSession = Depends(get_db),
) -> Store:
    return await transition_store_publication(
        store_id=store_id,
        payload=payload,
        current_admin=current_admin,
        db=db,
        target_status="published",
    )


@router.post(
    "/{store_id}/unpublish",
    response_model=StoreResponse,
)
async def unpublish_store(
    store_id: UUID,
    payload: AdminStorePublicationRequest,
    current_admin: User = Depends(
        require_platform_admin
    ),
    db: AsyncSession = Depends(get_db),
) -> Store:
    return await transition_store_publication(
        store_id=store_id,
        payload=payload,
        current_admin=current_admin,
        db=db,
        target_status="draft",
    )
