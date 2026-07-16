from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_store_owner, require_platform_admin
from app.core.config import settings
from app.db.session import get_db
from app.models import (
    Product,
    Store,
    StoreAccessEvent,
    SubscriptionPayment,
    SubscriptionPlan,
    User,
)
from app.schemas.store import StoreCreate, StoreResponse, StoreUpdate
from app.services.image_upload import (
    delete_managed_image_if_unreferenced,
    get_referenced_image_urls,
    persist_uploaded_image,
)
from app.services.image_upload_rate_limit import (
    enforce_image_upload_rate_limit,
)
from app.services.plan_features import ensure_plan_allows_image_uploads
from app.services.subscription import (
    build_subscription_request_fingerprint,
    get_subscription_extension_base,
    get_subscription_status_after_unsuspension,
)


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
        subscription_status="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=settings.TRIAL_DAYS),
    )

    try:
        db.add(store)
        await db.commit()
        await db.refresh(store)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Store slug is already taken",
        ) from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create the store.",
        ) from exc

    return store


@router.patch("/stores/{store_id}", response_model=StoreResponse)
async def update_store(
    payload: StoreUpdate,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    update_data = payload.model_dump(exclude_unset=True)

    previous_image_urls = {
        field_name: getattr(
            store,
            field_name,
        )
        for field_name in (
            "logo_url",
            "banner_url",
        )
        if field_name in update_data
    }

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

    try:
        await db.commit()
        await db.refresh(store)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Store slug is already taken",
        ) from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not update the store profile. "
                "Review the fields and try again."
            ),
        ) from exc

    for field_name, previous_url in (
        previous_image_urls.items()
    ):
        if (
            previous_url
            and previous_url
            != getattr(
                store,
                field_name,
            )
        ):
            await (
                delete_managed_image_if_unreferenced(
                    db=db,
                    store_id=store.id,
                    image_url=previous_url,
                )
            )

    return store


@router.get("/stores/{store_id}", response_model=StoreResponse)
async def get_store(
    store: Store = Depends(require_store_owner),
):
    return store






# ============================
# STORE LOGO / BANNER UPLOAD
# ============================


@router.post(
    "/stores/{store_id}/uploads/store-image"
)
async def upload_store_image(
    image_type: str = Form(...),
    file: UploadFile = File(...),
    store: Store = Depends(
        require_store_owner
    ),
    db: AsyncSession = Depends(get_db),
):
    if image_type not in {
        "logo",
        "banner",
    }:
        await file.close()

        raise HTTPException(
            status_code=400,
            detail=(
                "Image type must be logo "
                "or banner."
            ),
        )

    await ensure_plan_allows_image_uploads(
        db,
        store,
    )

    await enforce_image_upload_rate_limit(
        store.id
    )

    referenced_urls = (
        await get_referenced_image_urls(
            db,
            store.id,
        )
    )

    image_url = await persist_uploaded_image(
        upload=file,
        store_id=store.id,
        category=image_type,
        referenced_urls=referenced_urls,
    )

    return {
        "image_url": image_url,
        "image_type": image_type,
    }


# ============================
# ADMIN SUBSCRIPTION MANAGEMENT
# ============================

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AdminExtendSubscriptionPayload(BaseModel):
    plan_name: str | None = Field(
        default=None,
        pattern="^(starter|business|premium|custom)$",
    )
    amount_paid: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
    )
    extend_days: int = Field(default=30, ge=1, le=366)
    payment_method: str = Field(
        default="manual",
        pattern="^(manual|momo|bank|cash|paystack)$",
    )
    payment_reference: str | None = Field(
        default=None,
        max_length=100,
    )
    note: str | None = Field(default=None, max_length=500)
    mark_active: bool = True


@router.post("/admin/stores/{store_id}/subscription/extend", response_model=StoreResponse)
async def admin_extend_store_subscription(
    store_id: UUID,
    payload: AdminExtendSubscriptionPayload,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    normalized_idempotency_key = (
        idempotency_key.strip()
    )
    normalized_reference = (
        (payload.payment_reference or "").strip()
        or None
    )
    normalized_note = (
        (payload.note or "").strip()
        or None
    )
    normalized_payment_method = (
        payload.payment_method.lower().strip()
    )

    request_fingerprint = (
        build_subscription_request_fingerprint(
            store_id=store_id,
            approved_by_user_id=current_user.id,
            plan_name=payload.plan_name,
            amount_paid=payload.amount_paid,
            extend_days=payload.extend_days,
            payment_method=(
                normalized_payment_method
            ),
            payment_reference=(
                normalized_reference
            ),
            note=normalized_note,
            mark_active=payload.mark_active,
        )
    )

    result = await db.execute(
        select(Store)
        .where(Store.id == store_id)
        .with_for_update()
    )

    store = result.scalar_one_or_none()

    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    existing_payment_result = await db.execute(
        select(SubscriptionPayment).where(
            SubscriptionPayment.store_id
            == store.id,
            SubscriptionPayment.idempotency_key
            == normalized_idempotency_key,
        )
    )
    existing_payment = (
        existing_payment_result.scalar_one_or_none()
    )

    if existing_payment is not None:
        if (
            existing_payment.request_fingerprint
            != request_fingerprint
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This idempotency key was already used "
                    "for a different subscription request."
                ),
            )

        await db.commit()
        await db.refresh(store)
        return store

    external_reference_methods = {
        "momo",
        "bank",
        "paystack",
    }

    if (
        normalized_payment_method
        in external_reference_methods
        and normalized_reference is None
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "A payment reference is required for "
                f"{normalized_payment_method} payments."
            ),
        )

    if (
        normalized_payment_method
        in external_reference_methods
    ):
        reference_result = await db.execute(
            select(SubscriptionPayment).where(
                SubscriptionPayment.payment_method
                == normalized_payment_method,
                func.lower(
                    func.btrim(
                        SubscriptionPayment.payment_reference
                    )
                )
                == normalized_reference.lower(),
            )
        )
        reference_payment = (
            reference_result.scalar_one_or_none()
        )

        if reference_payment is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This payment reference has already been recorded."
                ),
            )

    requested_plan_name = (
        payload.plan_name
        or store.plan_name
        or "starter"
    ).lower().strip()

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

    if not payload.mark_active:
        raise HTTPException(
            status_code=400,
            detail=(
                "Paid subscription extensions must activate the store subscription."
            ),
        )

    base_date = get_subscription_extension_base(
        store,
        now,
    )

    resolved_monthly_fee = plan.monthly_fee
    amount_paid = (
        payload.amount_paid
        if payload.amount_paid is not None
        else resolved_monthly_fee
    )

    if amount_paid <= 0:
        raise HTTPException(
            status_code=422,
            detail=(
                "Enter the amount received for this paid subscription."
            ),
        )

    store.plan_name = plan.name
    store.monthly_fee = resolved_monthly_fee
    store.last_payment_at = now
    store.subscription_ends_at = base_date + timedelta(days=payload.extend_days)

    if not store.trial_ends_at:
        store.trial_ends_at = now

    store.subscription_status = "active"

    # Recording payment changes billing state only.
    # Operational activation and suspension require
    # the dedicated admin store-status transition.
    subscription_payment = SubscriptionPayment(
        store_id=store.id,
        approved_by_user_id=current_user.id,
        plan_name=plan.name,
        amount=amount_paid,
        currency="GHS",
        payment_method=(
            normalized_payment_method
        ),
        payment_reference=(
            normalized_reference
        ),
        idempotency_key=(
            normalized_idempotency_key
        ),
        request_fingerprint=(
            request_fingerprint
        ),
        note=normalized_note,
        covered_days=payload.extend_days,
        paid_at=now,
    )

    db.add(subscription_payment)

    try:
        await db.commit()
        await db.refresh(store)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "This subscription payment request was already processed."
            ),
        ) from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not record the subscription payment. "
                "No subscription change was saved."
            ),
        ) from exc

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
    trial_ends_at: datetime | None = None
    subscription_ends_at: datetime | None = None
    last_payment_at: datetime | None = None
    is_active: bool
    is_suspended: bool
    publication_status: str


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
            trial_ends_at=store.trial_ends_at,
            subscription_ends_at=store.subscription_ends_at,
            last_payment_at=store.last_payment_at,
            is_active=store.is_active,
            is_suspended=store.is_suspended,
            publication_status=store.publication_status,
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
    is_active: bool | None = None
    is_suspended: bool | None = None
    note: str | None = Field(
        default=None,
        max_length=500,
    )

    model_config = ConfigDict(
        extra="forbid"
    )


def _derive_store_access_action(
    *,
    previous_is_active: bool,
    new_is_active: bool,
    previous_is_suspended: bool,
    new_is_suspended: bool,
) -> str:
    if (
        previous_is_suspended
        != new_is_suspended
    ):
        return (
            "suspend"
            if new_is_suspended
            else "unsuspend"
        )

    if previous_is_active != new_is_active:
        return (
            "activate"
            if new_is_active
            else "deactivate"
        )

    raise ValueError(
        "Store access state did not change."
    )


@router.patch("/admin/stores/{store_id}/status", response_model=StoreResponse)
async def admin_update_store_status(
    store_id: UUID,
    payload: AdminStoreStatusUpdate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    if (
        payload.is_active is None
        and payload.is_suspended is None
    ):
        raise HTTPException(
            status_code=400,
            detail="No store status change was requested.",
        )

    try:
        result = await db.execute(
            select(Store)
            .where(Store.id == store_id)
            .with_for_update()
        )

        store = result.scalar_one_or_none()

        if not store:
            raise HTTPException(
                status_code=404,
                detail="Store not found.",
            )

        previous_is_active = bool(
            store.is_active
        )
        previous_is_suspended = bool(
            store.is_suspended
        )
        previous_subscription_status = (
            store.subscription_status
        )

        if payload.is_active is not None:
            store.is_active = payload.is_active

        if payload.is_suspended is not None:
            store.is_suspended = (
                payload.is_suspended
            )

            if (
                previous_is_suspended
                and not store.is_suspended
            ):
                store.subscription_status = (
                    get_subscription_status_after_unsuspension(
                        store
                    )
                )

        new_is_active = bool(
            store.is_active
        )
        new_is_suspended = bool(
            store.is_suspended
        )

        if (
            previous_is_active
            == new_is_active
            and previous_is_suspended
            == new_is_suspended
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Store access status is already "
                    "set to the requested state."
                ),
            )

        changed_at = datetime.now(
            timezone.utc
        )
        normalized_note = (
            (payload.note or "").strip()
            or None
        )

        event = StoreAccessEvent(
            store_id=store.id,
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            action=_derive_store_access_action(
                previous_is_active=(
                    previous_is_active
                ),
                new_is_active=new_is_active,
                previous_is_suspended=(
                    previous_is_suspended
                ),
                new_is_suspended=(
                    new_is_suspended
                ),
            ),
            previous_is_active=(
                previous_is_active
            ),
            new_is_active=new_is_active,
            previous_is_suspended=(
                previous_is_suspended
            ),
            new_is_suspended=(
                new_is_suspended
            ),
            previous_subscription_status=(
                previous_subscription_status
            ),
            new_subscription_status=(
                store.subscription_status
            ),
            reason=normalized_note,
            created_at=changed_at,
        )

        store.updated_at = changed_at
        db.add(event)

        await db.flush()
        await db.commit()

        return store

    except HTTPException:
        await db.rollback()
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not update the store access status."
            ),
        ) from exc
    except Exception:
        await db.rollback()
        raise


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

        end_at = (
            store.trial_ends_at
            if status == "trial"
            else store.subscription_ends_at
        )
        if end_at and end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)

        if store.is_suspended or status == "suspended":
            suspended_stores += 1
            continue

        if status == "expired" or (
            status in {"trial", "active"}
            and (
                end_at is None
                or end_at <= now
            )
        ):
            expired_stores += 1
            continue

        if status == "trial":
            trial_stores += 1
        elif status == "active":
            active_stores += 1
            monthly_recurring_total += store.monthly_fee or Decimal("0.00")

        if status in {"trial", "active"}:
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
    is_quote_only: bool
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
    is_quote_only: bool | None = None
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
        is_quote_only=plan.is_quote_only,
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

    next_is_quote_only = update_data.get(
        "is_quote_only",
        plan.is_quote_only,
    )

    if next_is_quote_only:
        update_data["monthly_fee"] = Decimal("0.00")

    for key, value in update_data.items():
        setattr(plan, key, value)

    await db.commit()
    await db.refresh(plan)

    return subscription_plan_to_item(plan)

class StoreSubscriptionUsageResponse(BaseModel):
    plan_name: str
    display_name: str
    monthly_fee: Decimal
    is_quote_only: bool
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
        is_quote_only = bool(plan.is_quote_only)
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
        is_quote_only = plan_name == "custom"
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
        is_quote_only=is_quote_only,
        product_limit=product_limit,
        active_products=active_products,
        remaining_products=remaining_products,
        is_unlimited=is_unlimited,
        can_upload_images=can_upload_images,
        can_use_custom_domain=can_use_custom_domain,
        can_receive_online_payments=(
            settings.PAYMENTS_ENABLED
            and can_receive_online_payments
        ),
        plan_is_active=plan_is_active,
    )

class AdminStorePlanUpdate(BaseModel):
    plan_name: str = Field(min_length=1, max_length=50)


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
