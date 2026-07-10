from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Store, SubscriptionPlan


DEFAULT_PLAN_FEATURES: dict[str, dict[str, bool]] = {
    "starter": {
        "can_upload_images": True,
        "can_use_custom_domain": False,
        "can_receive_online_payments": True,
    },
    "business": {
        "can_upload_images": True,
        "can_use_custom_domain": False,
        "can_receive_online_payments": True,
    },
    "premium": {
        "can_upload_images": True,
        "can_use_custom_domain": True,
        "can_receive_online_payments": True,
    },
    "custom": {
        "can_upload_images": True,
        "can_use_custom_domain": True,
        "can_receive_online_payments": True,
    },
}


async def get_subscription_plan_for_store(
    db: AsyncSession,
    store: Store,
) -> SubscriptionPlan | None:
    plan_name = (store.plan_name or "starter").lower().strip()

    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == plan_name)
    )

    return result.scalar_one_or_none()


def get_default_feature_value(plan_name: str | None, feature_name: str) -> bool:
    normalized_plan_name = (plan_name or "starter").lower().strip()
    plan_features = DEFAULT_PLAN_FEATURES.get(
        normalized_plan_name,
        DEFAULT_PLAN_FEATURES["starter"],
    )

    return bool(plan_features.get(feature_name, False))


async def get_plan_feature_value(
    db: AsyncSession,
    store: Store,
    feature_name: str,
) -> bool:
    plan = await get_subscription_plan_for_store(db, store)

    if plan:
        if not plan.is_active:
            raise HTTPException(
                status_code=403,
                detail="This subscription plan is currently inactive.",
            )

        return bool(getattr(plan, feature_name))

    return get_default_feature_value(store.plan_name, feature_name)


async def ensure_plan_allows_image_uploads(
    db: AsyncSession,
    store: Store,
) -> None:
    allowed = await get_plan_feature_value(db, store, "can_upload_images")

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Your current plan does not allow image uploads. Upgrade your plan to upload images.",
        )


async def ensure_plan_allows_online_payments(
    db: AsyncSession,
    store: Store,
) -> None:
    allowed = await get_plan_feature_value(db, store, "can_receive_online_payments")

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Your current plan does not allow online payments. Contact support or upgrade your plan.",
        )


async def ensure_plan_allows_custom_domain(
    db: AsyncSession,
    store: Store,
) -> None:
    allowed = await get_plan_feature_value(db, store, "can_use_custom_domain")

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Your current plan does not allow custom domains. Upgrade your plan to connect a custom domain.",
        )