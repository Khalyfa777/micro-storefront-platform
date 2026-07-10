from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_store_owner, require_platform_admin
from app.db.session import get_db
from app.models import Store, User, SubscriptionPayment, SubscriptionPlan, Product
from app.schemas.store import StoreCreate, StoreResponse, StoreUpdate
from app.services.plan_features import ensure_plan_allows_image_uploads


router = APIRouter(tags=["stores"])


@router.get("/stores/", response_model=list[StoreResponse])
async def list_my_stores(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Store)
        .where(Store.owner_id == current_user.id)
        .order_by(Store.created_at.desc())
    )

    return result.scalars().all()


@router.post("/stores/", response_model=StoreResponse)
async def create_store(
    payload: StoreCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing_result = await db.execute(
        select(Store).where(Store.slug == payload.slug)
    )
    existing_store = existing_result.scalar_one_or_none()

    if existing_store:
        raise HTTPException(status_code=400, detail="Store slug is already taken")

    store = Store(
        owner_id=current_user.id,
        slug=payload.slug,
        name=payload.name,
        bio=payload.bio,
        logo_url=payload.logo_url,
        banner_url=payload.banner_url,
        whatsapp_number=payload.whatsapp_number,
        social_links=payload.social_links,
        category=payload.category,
        theme=payload.theme,
    )

    db.add(store)
    await db.commit()
    await db.refresh(store)

    return store


@router.patch("/stores/{store_id}", response_model=StoreResponse)
async def update_store(
    payload: StoreUpdate,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    update_data = payload.model_dump(exclude_unset=True)

    if "slug" in update_data and update_data["slug"] != store.slug:
        existing_result = await db.execute(
            select(Store).where(
                Store.slug == update_data["slug"],
                Store.id != store.id,
            )
        )
        existing_store = existing_result.scalar_one_or_none()

        if existing_store:
            raise HTTPException(status_code=400, detail="Store slug is already taken")

    for key, value in update_data.items():
        setattr(store, key, value)

    await db.commit()
    await db.refresh(store)

    return store


@router.get("/stores/{store_id}", response_model=StoreResponse)
async def get_store(
    store: Store = Depends(require_store_owner),
):
    return store






# ============================
# STORE LOGO / BANNER UPLOAD
# ============================

import base64
import binascii
import io
import os
from uuid import uuid4

from PIL import Image
from pydantic import BaseModel, Field

from app.core.config import settings


class StoreImageUploadPayload(BaseModel):
    filename: str
    content_type: str
    image_type: str = Field(pattern="^(logo|banner)$")
    data_base64: str = Field(min_length=1)


@router.post("/stores/{store_id}/uploads/store-image")
async def upload_store_image(
    payload: StoreImageUploadPayload,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    await ensure_plan_allows_image_uploads(db, store)

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    if payload.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG, and WEBP images are allowed.",
        )

    try:
        image_bytes = base64.b64decode(payload.data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid image data.")

    max_size_bytes = 3 * 1024 * 1024

    if len(image_bytes) > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail="Image is too large. Maximum size is 3MB.",
        )

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is not a valid image.",
        )

    upload_dir = f"static/uploads/stores/{payload.image_type}s"
    os.makedirs(upload_dir, exist_ok=True)

    extension = allowed_types[payload.content_type]
    safe_filename = f"{store.id}-{payload.image_type}-{uuid4().hex}{extension}"
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as file:
        file.write(image_bytes)

    image_url = f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/{file_path.replace(os.sep, '/')}"

    return {
        "image_url": image_url,
        "image_type": payload.image_type,
    }

# ============================
# ADMIN SUBSCRIPTION MANAGEMENT
# ============================

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel, Field


class AdminExtendSubscriptionPayload(BaseModel):
    plan_name: str | None = Field(
        default=None,
        pattern="^(starter|business|premium|custom)$",
    )
    monthly_fee: Decimal | None = Field(default=None, ge=0)
    amount_paid: Decimal | None = Field(default=None, ge=0)
    extend_days: int = Field(default=30, ge=1, le=366)
    payment_method: str = Field(default="manual", pattern="^(manual|momo|bank|cash|paystack)$")
    payment_reference: str | None = Field(default=None, max_length=100)
    note: str | None = None
    mark_active: bool = True


@router.post("/admin/stores/{store_id}/subscription/extend", response_model=StoreResponse)
async def admin_extend_store_subscription(
    store_id: UUID,
    payload: AdminExtendSubscriptionPayload,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .with_for_update()
    )

    store = result.scalar_one_or_none()

    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    requested_plan_name = (payload.plan_name or store.plan_name or "starter").lower().strip()

    plan_result = await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.name == requested_plan_name)
        .with_for_update()
    )
    plan = plan_result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")

    if not plan.is_active:
        raise HTTPException(status_code=400, detail="This subscription plan is inactive.")

    now = datetime.now(timezone.utc)

    current_end = store.subscription_ends_at

    if current_end and current_end.tzinfo is None:
        current_end = current_end.replace(tzinfo=timezone.utc)

    base_date = current_end if current_end and current_end > now else now

    resolved_monthly_fee = plan.monthly_fee
    amount_paid = payload.amount_paid if payload.amount_paid is not None else resolved_monthly_fee

    store.plan_name = plan.name
    store.monthly_fee = resolved_monthly_fee
    store.last_payment_at = now
    store.subscription_ends_at = base_date + timedelta(days=payload.extend_days)

    if not store.trial_ends_at:
        store.trial_ends_at = now

    if payload.mark_active:
        store.subscription_status = "active"
        store.is_suspended = False
        store.is_active = True

    subscription_payment = SubscriptionPayment(
        store_id=store.id,
        approved_by_user_id=current_user.id,
        plan_name=plan.name,
        amount=amount_paid,
        currency="GHS",
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
        note=payload.note,
        covered_days=payload.extend_days,
        paid_at=now,
    )

    db.add(subscription_payment)

    await db.commit()
    await db.refresh(store)

    return store
class AdminStoreListItem(BaseModel):
    id: UUID
    owner_id: UUID
    owner_email: str
    owner_name: str
    slug: str
    name: str
    plan_name: str
    subscription_status: str
    monthly_fee: Decimal
    subscription_ends_at: datetime | None = None
    last_payment_at: datetime | None = None
    is_active: bool
    is_suspended: bool


@router.get("/admin/stores", response_model=list[AdminStoreListItem])
async def admin_list_all_stores(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # Auto-sync expired subscriptions before returning admin store list.
    await db.execute(
        update(Store)
        .where(
            Store.subscription_status == "active",
            Store.subscription_ends_at.is_not(None),
            Store.subscription_ends_at <= now,
            Store.is_suspended.is_(False),
        )
        .values(subscription_status="expired")
    )

    await db.commit()

    result = await db.execute(
        select(Store, User.email, User.full_name)
        .join(User, User.id == Store.owner_id)
        .order_by(Store.created_at.desc())
    )

    rows = result.all()

    return [
        AdminStoreListItem(
            id=store.id,
            owner_id=store.owner_id,
            owner_email=owner_email,
            owner_name=owner_name,
            slug=store.slug,
            name=store.name,
            plan_name=store.plan_name,
            subscription_status=store.subscription_status,
            monthly_fee=store.monthly_fee,
            subscription_ends_at=store.subscription_ends_at,
            last_payment_at=store.last_payment_at,
            is_active=store.is_active,
            is_suspended=store.is_suspended,
        )
        for store, owner_email, owner_name in rows
    ]

class AdminSubscriptionPaymentItem(BaseModel):
    id: UUID
    store_id: UUID
    store_name: str
    store_slug: str
    plan_name: str
    amount: Decimal
    currency: str
    payment_method: str
    payment_reference: str | None = None
    note: str | None = None
    covered_days: int
    approved_by_email: str | None = None
    paid_at: datetime
    created_at: datetime


@router.get("/admin/subscription-payments", response_model=list[AdminSubscriptionPaymentItem])
async def admin_list_subscription_payments(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            SubscriptionPayment,
            Store.name,
            Store.slug,
            User.email,
        )
        .join(Store, Store.id == SubscriptionPayment.store_id)
        .outerjoin(User, User.id == SubscriptionPayment.approved_by_user_id)
        .order_by(SubscriptionPayment.created_at.desc())
        .limit(100)
    )

    rows = result.all()

    return [
        AdminSubscriptionPaymentItem(
            id=payment.id,
            store_id=payment.store_id,
            store_name=store_name,
            store_slug=store_slug,
            plan_name=payment.plan_name,
            amount=payment.amount,
            currency=payment.currency,
            payment_method=payment.payment_method,
            payment_reference=payment.payment_reference,
            note=payment.note,
            covered_days=payment.covered_days,
            approved_by_email=approved_by_email,
            paid_at=payment.paid_at,
            created_at=payment.created_at,
        )
        for payment, store_name, store_slug, approved_by_email in rows
    ]

class AdminStoreStatusUpdate(BaseModel):
    subscription_status: str | None = Field(
        default=None,
        pattern="^(trial|active|expired|suspended)$",
    )
    is_active: bool | None = None
    is_suspended: bool | None = None
    note: str | None = None


@router.patch("/admin/stores/{store_id}/status", response_model=StoreResponse)
async def admin_update_store_status(
    store_id: UUID,
    payload: AdminStoreStatusUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .with_for_update()
    )

    store = result.scalar_one_or_none()

    if not store:
        raise HTTPException(status_code=404, detail="Store not found.")

    if payload.subscription_status is not None:
        store.subscription_status = payload.subscription_status

    if payload.is_active is not None:
        store.is_active = payload.is_active

    if payload.is_suspended is not None:
        store.is_suspended = payload.is_suspended

    await db.commit()
    await db.refresh(store)

    return store

class AdminSubscriptionSummary(BaseModel):
    total_stores: int
    active_stores: int
    trial_stores: int
    expired_stores: int
    suspended_stores: int
    expiring_within_7_days: int
    monthly_recurring_total: Decimal
    subscription_revenue_total: Decimal
    subscription_revenue_this_month: Decimal
    recent_payment_count: int


@router.get("/admin/subscription-summary", response_model=AdminSubscriptionSummary)
async def admin_subscription_summary(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # Auto-sync expired subscriptions before calculating summary.
    await db.execute(
        update(Store)
        .where(
            Store.subscription_status == "active",
            Store.subscription_ends_at.is_not(None),
            Store.subscription_ends_at <= now,
            Store.is_suspended.is_(False),
        )
        .values(subscription_status="expired")
    )

    await db.commit()

    stores_result = await db.execute(select(Store))
    stores = list(stores_result.scalars().all())

    payments_result = await db.execute(select(SubscriptionPayment))
    payments = list(payments_result.scalars().all())

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_stores = len(stores)
    active_stores = 0
    trial_stores = 0
    expired_stores = 0
    suspended_stores = 0
    expiring_within_7_days = 0
    monthly_recurring_total = Decimal("0.00")

    for store in stores:
        status = store.subscription_status or "trial"

        end_at = store.subscription_ends_at
        if end_at and end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)

        if store.is_suspended or status == "suspended":
            suspended_stores += 1
            continue

        if status == "expired" or (end_at and end_at <= now):
            expired_stores += 1
            continue

        if status == "trial":
            trial_stores += 1
        elif status == "active":
            active_stores += 1
            monthly_recurring_total += store.monthly_fee or Decimal("0.00")

            if end_at:
                days_left = (end_at - now).days
                if 0 <= days_left <= 7:
                    expiring_within_7_days += 1

    subscription_revenue_total = Decimal("0.00")
    subscription_revenue_this_month = Decimal("0.00")

    for payment in payments:
        subscription_revenue_total += payment.amount or Decimal("0.00")

        created_at = payment.created_at
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if created_at and created_at >= month_start:
            subscription_revenue_this_month += payment.amount or Decimal("0.00")

    return AdminSubscriptionSummary(
        total_stores=total_stores,
        active_stores=active_stores,
        trial_stores=trial_stores,
        expired_stores=expired_stores,
        suspended_stores=suspended_stores,
        expiring_within_7_days=expiring_within_7_days,
        monthly_recurring_total=monthly_recurring_total,
        subscription_revenue_total=subscription_revenue_total,
        subscription_revenue_this_month=subscription_revenue_this_month,
        recent_payment_count=len(payments),
    )

class AdminSubscriptionPlanItem(BaseModel):
    id: UUID
    name: str
    display_name: str
    monthly_fee: Decimal
    product_limit: int | None = None
    can_upload_images: bool
    can_use_custom_domain: bool
    can_receive_online_payments: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminSubscriptionPlanUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    monthly_fee: Decimal | None = Field(default=None, ge=0)
    product_limit: int | None = Field(default=None, ge=0)
    can_upload_images: bool | None = None
    can_use_custom_domain: bool | None = None
    can_receive_online_payments: bool | None = None
    is_active: bool | None = None


def subscription_plan_to_item(plan: SubscriptionPlan) -> AdminSubscriptionPlanItem:
    return AdminSubscriptionPlanItem(
        id=plan.id,
        name=plan.name,
        display_name=plan.display_name,
        monthly_fee=plan.monthly_fee,
        product_limit=plan.product_limit,
        can_upload_images=plan.can_upload_images,
        can_use_custom_domain=plan.can_use_custom_domain,
        can_receive_online_payments=plan.can_receive_online_payments,
        is_active=plan.is_active,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


@router.get("/admin/subscription-plans", response_model=list[AdminSubscriptionPlanItem])
async def admin_list_subscription_plans(
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SubscriptionPlan)
        .order_by(SubscriptionPlan.monthly_fee.asc(), SubscriptionPlan.name.asc())
    )

    return [
        subscription_plan_to_item(plan)
        for plan in result.scalars().all()
    ]


@router.patch("/admin/subscription-plans/{plan_name}", response_model=AdminSubscriptionPlanItem)
async def admin_update_subscription_plan(
    plan_name: str,
    payload: AdminSubscriptionPlanUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    normalized_plan_name = plan_name.lower().strip()

    result = await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.name == normalized_plan_name)
        .with_for_update()
    )

    plan = result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")

    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(plan, key, value)

    await db.commit()
    await db.refresh(plan)

    return subscription_plan_to_item(plan)

class StoreSubscriptionUsageResponse(BaseModel):
    plan_name: str
    display_name: str
    monthly_fee: Decimal
    product_limit: int | None = None
    active_products: int
    remaining_products: int | None = None
    is_unlimited: bool
    can_upload_images: bool
    can_use_custom_domain: bool
    can_receive_online_payments: bool
    plan_is_active: bool


@router.get("/stores/{store_id}/subscription-usage", response_model=StoreSubscriptionUsageResponse)
async def get_store_subscription_usage(
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    active_count_result = await db.execute(
        select(func.count(Product.id)).where(
            Product.store_id == store.id,
            Product.is_active.is_(True),
        )
    )

    active_products = active_count_result.scalar_one()

    plan_name = (store.plan_name or "starter").lower().strip()

    plan_result = await db.execute(
        select(SubscriptionPlan).where(
            SubscriptionPlan.name == plan_name,
        )
    )

    plan = plan_result.scalar_one_or_none()

    if plan:
        plan_is_active = bool(plan.is_active)
        product_limit = plan.product_limit
        display_name = plan.display_name
        monthly_fee = plan.monthly_fee
        can_upload_images = bool(plan.can_upload_images) if plan_is_active else False
        can_use_custom_domain = bool(plan.can_use_custom_domain) if plan_is_active else False
        can_receive_online_payments = bool(plan.can_receive_online_payments) if plan_is_active else False
    else:
        fallback_limits = {
            "starter": 10,
            "business": 100,
            "premium": None,
            "custom": None,
        }

        fallback_features = {
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

        product_limit = fallback_limits.get(plan_name, 10)
        display_name = plan_name.title()
        monthly_fee = store.monthly_fee
        plan_is_active = True
        feature_set = fallback_features.get(plan_name, fallback_features["starter"])
        can_upload_images = feature_set["can_upload_images"]
        can_use_custom_domain = feature_set["can_use_custom_domain"]
        can_receive_online_payments = feature_set["can_receive_online_payments"]

    is_unlimited = product_limit is None
    remaining_products = None if is_unlimited else max(product_limit - active_products, 0)

    return StoreSubscriptionUsageResponse(
        plan_name=plan_name,
        display_name=display_name,
        monthly_fee=monthly_fee,
        product_limit=product_limit,
        active_products=active_products,
        remaining_products=remaining_products,
        is_unlimited=is_unlimited,
        can_upload_images=can_upload_images,
        can_use_custom_domain=can_use_custom_domain,
        can_receive_online_payments=can_receive_online_payments,
        plan_is_active=plan_is_active,
    )

class AdminStorePlanUpdate(BaseModel):
    plan_name: str = Field(min_length=1, max_length=50)
    monthly_fee: Decimal | None = Field(default=None, ge=0)


class AdminStorePlanResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    plan_name: str
    monthly_fee: Decimal
    subscription_status: str
    subscription_ends_at: datetime | None = None


@router.patch("/admin/stores/{store_id}/plan", response_model=AdminStorePlanResponse)
async def admin_update_store_plan(
    store_id: UUID,
    payload: AdminStorePlanUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    normalized_plan_name = payload.plan_name.lower().strip()

    plan_result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.name == normalized_plan_name)
    )
    plan = plan_result.scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Subscription plan not found.")

    if not plan.is_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot move seller to an inactive subscription plan.",
        )

    store_result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .with_for_update()
    )
    store = store_result.scalar_one_or_none()

    if not store:
        raise HTTPException(status_code=404, detail="Store not found.")

    store.plan_name = plan.name
    store.monthly_fee = plan.monthly_fee

    await db.commit()
    await db.refresh(store)

    return AdminStorePlanResponse(
        id=store.id,
        name=store.name,
        slug=store.slug,
        plan_name=store.plan_name,
        monthly_fee=store.monthly_fee,
        subscription_status=store.subscription_status,
        subscription_ends_at=store.subscription_ends_at,
    )