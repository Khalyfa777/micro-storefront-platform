from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Store, Product, SubscriptionPlan
from app.schemas.product import ProductResponse
from app.schemas.store import StorePublicResponse
from app.services.subscription import get_store_access_error


router = APIRouter(tags=["public"])



async def get_public_online_payment_flag(db: AsyncSession, store: Store) -> bool:
    plan_name = (store.plan_name or "").lower().strip()

    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == plan_name)
    )

    plan = result.scalar_one_or_none()

    if plan:
        if not plan.is_active:
            return False

        return bool(plan.can_receive_online_payments)

    fallback_online_payment_flags = {
        "starter": True,
        "business": True,
        "premium": True,
        "custom": True,
    }

    return fallback_online_payment_flags.get(plan_name, False)
class PublicStorePayload(BaseModel):
    store: StorePublicResponse
    products: list[ProductResponse]


@router.get("/public/stores/{slug}", response_model=PublicStorePayload)
async def public_store(slug: str, db: AsyncSession = Depends(get_db)):
    store_result = await db.execute(
        select(Store).where(Store.slug == slug)
    )

    store = store_result.scalar_one_or_none()

    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    publication_status = (
        store.publication_status or "draft"
    ).lower().strip()

    if publication_status != "published":
        # Draft stores must not disclose their existence publicly.
        raise HTTPException(
            status_code=404,
            detail="Store not found",
        )

    access_error = get_store_access_error(store)

    if access_error:
        raise HTTPException(status_code=403, detail=access_error)

    store.can_receive_online_payments = await get_public_online_payment_flag(db, store)

    products_result = await db.execute(
        select(Product).where(
            Product.store_id == store.id,
            Product.is_active == True,
        )
    )

    products = products_result.scalars().all()

    return {
        "store": store,
        "products": products,
    }
