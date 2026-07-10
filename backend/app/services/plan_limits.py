from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Store, SubscriptionPlan


DEFAULT_PRODUCT_LIMITS: dict[str, int | None] = {
    "starter": 10,
    "business": 100,
    "premium": None,
    "custom": None,
}


async def get_product_limit_for_store(
    db: AsyncSession,
    store: Store,
) -> int | None:
    plan_name = (store.plan_name or "starter").lower().strip()

    result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.name == plan_name,
            SubscriptionPlan.is_active.is_(True),
        )
    )

    plan = result.scalar_one_or_none()

    if plan:
        return plan.product_limit

    return DEFAULT_PRODUCT_LIMITS.get(plan_name, DEFAULT_PRODUCT_LIMITS["starter"])


def get_product_limit_message(plan_name: str | None, limit: int) -> str:
    readable_plan = (plan_name or "starter").title()

    return (
        f"{readable_plan} plan allows up to {limit} active products. "
        "Upgrade your plan to add more active products."
    )