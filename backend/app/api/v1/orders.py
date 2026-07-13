import hmac
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_store_owner
from app.db.session import get_db
from app.models import Store, Product, Order, OrderItem
from app.schemas.order import (
    OrderResponse,
    OrderStatusUpdate,
    PublicOrderCreate,
    PublicOrderTrackingResponse,
    PublicOrderTrackRequest,
)
from app.services.subscription import get_store_access_error
from app.services.store_publication import is_store_published
from app.services.order_tracking import (
    PUBLIC_NO_STORE_HEADERS,
    apply_public_no_store_headers,
    normalize_customer_phone,
)
from app.services.order_tracking_rate_limit import (
    enforce_order_tracking_rate_limit,
)
from app.services.order_idempotency import (
    acquire_order_idempotency_lock,
    build_order_request_fingerprint,
    normalize_order_idempotency_key,
)


router = APIRouter(tags=["orders"])

ORDER_STATUS_TRANSITIONS = {
    "pending": {"paid", "cancelled"},
    "paid": {"processing", "completed", "cancelled"},
    "processing": {"completed", "cancelled"},
    "completed": {"cancelled"},
    "cancelled": set(),
}


def ensure_order_status_transition_allowed(current_status: str, new_status: str) -> None:
    current = (current_status or "").lower()
    new = (new_status or "").lower()

    if current == new:
        return

    allowed_next_statuses = ORDER_STATUS_TRANSITIONS.get(current)

    if allowed_next_statuses is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown current order status: {current_status}",
        )

    if new not in allowed_next_statuses:
        allowed_display = ", ".join(sorted(allowed_next_statuses)) or "no further changes"

        raise HTTPException(
            status_code=400,
            detail=f"Invalid order status transition from {current} to {new}. Allowed next status: {allowed_display}.",
        )


def generate_order_number() -> str:
    return f"ORD-{uuid4().hex[:10].upper()}"


@router.post(
    "/public/orders",
    response_model=OrderResponse,
)
async def create_public_order(
    payload: PublicOrderCreate,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        normalized_idempotency_key = (
            normalize_order_idempotency_key(
                idempotency_key
            )
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    request_fingerprint = (
        build_order_request_fingerprint(
            payload.model_dump(
                mode="json"
            )
        )
    )

    store_result = await db.execute(
        select(Store)
        .where(
            Store.slug == payload.store_slug
        )
        .with_for_update(read=True)
    )

    store = store_result.scalar_one_or_none()

    if not store:
        raise HTTPException(
            status_code=404,
            detail="Store not found",
        )

    # Serialize requests only when the same
    # store and idempotency key are reused.
    await acquire_order_idempotency_lock(
        db,
        store.id,
        normalized_idempotency_key,
    )

    existing_result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items)
        )
        .where(
            Order.store_id == store.id,
            Order.idempotency_key
            == normalized_idempotency_key,
        )
    )

    existing_order = (
        existing_result.scalar_one_or_none()
    )

    if existing_order is not None:
        existing_fingerprint = (
            existing_order.request_fingerprint
            or ""
        )

        if not hmac.compare_digest(
            existing_fingerprint,
            request_fingerprint,
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This Idempotency-Key was "
                    "already used with different "
                    "order details."
                ),
            )

        return existing_order

    if not is_store_published(store):
        # New orders remain concealed when the
        # storefront is not published.
        raise HTTPException(
            status_code=404,
            detail="Store not found",
        )

    access_error = get_store_access_error(
        store
    )

    if access_error:
        raise HTTPException(
            status_code=403,
            detail=access_error,
        )

    product_ids = [
        item.product_id
        for item in payload.items
    ]

    products_result = await db.execute(
        select(Product).where(
            Product.store_id == store.id,
            Product.id.in_(product_ids),
            Product.is_active == True,
        )
    )

    products = {
        product.id: product
        for product
        in products_result.scalars().all()
    }

    prepared_items = []
    subtotal = Decimal("0.00")

    for item in payload.items:
        product = products.get(
            item.product_id
        )

        if not product:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Product not available: "
                    f"{item.product_id}"
                ),
            )

        if (
            product.stock_quantity is not None
            and item.quantity
            > product.stock_quantity
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only "
                    f"{product.stock_quantity} "
                    f"left in stock for "
                    f"{product.name}"
                ),
            )

        line_total = (
            product.price * item.quantity
        )

        subtotal += line_total

        prepared_items.append(
            {
                "product": product,
                "quantity": item.quantity,
                "line_total": line_total,
            }
        )

    order = Order(
        store_id=store.id,
        order_number=generate_order_number(),
        idempotency_key=(
            normalized_idempotency_key
        ),
        request_fingerprint=(
            request_fingerprint
        ),
        status="pending",
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        delivery_address=(
            payload.delivery_address
        ),
        customer_note=payload.customer_note,
        subtotal=subtotal,
        delivery_fee=Decimal("0.00"),
        total=subtotal,
        currency="GHS",
    )

    db.add(order)
    await db.flush()

    for prepared in prepared_items:
        product = prepared["product"]
        quantity = prepared["quantity"]
        line_total = prepared["line_total"]

        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                unit_price=product.price,
                quantity=quantity,
                line_total=line_total,
            )
        )

    await db.commit()

    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.items)
        )
        .where(Order.id == order.id)
    )

    return result.scalar_one()



@router.post(
    "/public/orders/track",
    response_model=(
        PublicOrderTrackingResponse
    ),
)
async def track_public_order(
    payload: PublicOrderTrackRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> PublicOrderTrackingResponse:
    apply_public_no_store_headers(
        response
    )

    await enforce_order_tracking_rate_limit(
        request
    )

    result = await db.execute(
        select(Order, Store.slug)
        .join(
            Store,
            Store.id == Order.store_id,
        )
        .options(
            selectinload(Order.items)
        )
        .where(
            Order.order_number
            == payload.order_number
        )
    )

    row = result.first()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Order not found. Check the "
                "order number and phone number."
            ),
            headers=PUBLIC_NO_STORE_HEADERS,
        )

    order, store_slug = row

    try:
        stored_phone = (
            normalize_customer_phone(
                order.customer_phone
            )
        )
    except (TypeError, ValueError):
        stored_phone = ""

    if not hmac.compare_digest(
        stored_phone,
        payload.customer_phone,
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "Order not found. Check the "
                "order number and phone number."
            ),
            headers=PUBLIC_NO_STORE_HEADERS,
        )

    return PublicOrderTrackingResponse(
        order_number=order.order_number,
        store_slug=store_slug,
        status=order.status,
        total=order.total,
        currency=order.currency,
        items=order.items,
        created_at=order.created_at,
    )

@router.get("/stores/{store_id}/orders/", response_model=list[OrderResponse])
async def list_store_orders(
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.store_id == store.id)
        .order_by(Order.created_at.desc())
    )

    return result.scalars().all()


@router.get("/stores/{store_id}/orders/{order_id}", response_model=OrderResponse)
async def get_store_order(
    order_id: str,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.store_id == store.id)
    )

    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


@router.patch("/stores/{store_id}/orders/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id, Order.store_id == store.id)
        .with_for_update()
    )

    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = payload.status.lower()
    previous_status = order.status
    ensure_order_status_transition_allowed(previous_status, new_status)
    should_deduct_inventory = new_status == "paid" and not order.inventory_deducted
    should_restore_inventory = (
        new_status == "cancelled"
        and order.inventory_deducted
        and previous_status in {"paid", "processing", "completed"}
    )

    order.status = new_status

    if new_status == "paid" and not order.payment_method:
        order.payment_method = "manual"

    if should_deduct_inventory:
        for item in order.items:
            product_result = await db.execute(
                select(Product)
                .where(
                    Product.id == item.product_id,
                    Product.store_id == store.id,
                )
                .with_for_update()
            )

            product = product_result.scalar_one_or_none()

            if not product:
                raise HTTPException(
                    status_code=400,
                    detail=f"Product not found for order item: {item.product_name}",
                )

            if product.stock_quantity is not None:
                if product.stock_quantity < item.quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Not enough stock for {product.name}. Available: {product.stock_quantity}",
                    )

                product.stock_quantity -= item.quantity

        order.inventory_deducted = True

    if should_restore_inventory:
        for item in order.items:
            product_result = await db.execute(
                select(Product)
                .where(
                    Product.id == item.product_id,
                    Product.store_id == store.id,
                )
                .with_for_update()
            )

            product = product_result.scalar_one_or_none()

            if not product:
                raise HTTPException(
                    status_code=400,
                    detail=f"Product not found for order item: {item.product_name}",
                )

            if product.stock_quantity is not None:
                product.stock_quantity += item.quantity

        order.inventory_deducted = False
    await db.commit()
    await db.refresh(order)

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )

    return result.scalar_one()
