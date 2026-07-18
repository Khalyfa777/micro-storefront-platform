import hmac
from decimal import Decimal
from typing import Annotated, Any, Iterable
from uuid import UUID, uuid4

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

from app.models import (
    Order,
    OrderItem,
    Product,
    ProductOrderField,
    Store,
)
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

from app.services.conversational_ordering import (
    build_whatsapp_order_summary,
    resolve_order_fulfillment_method,
    resolve_order_item_configuration,
    resolve_order_location,
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


def _aggregate_product_quantities(
    items: Iterable[Any],
) -> dict[UUID, int]:
    quantities: dict[UUID, int] = {}

    for item in items:
        product_id = item.product_id
        quantities[product_id] = (
            quantities.get(product_id, 0)
            + int(item.quantity)
        )

    return quantities


def _first_item_name_by_product(
    items: Iterable[Any],
) -> dict[UUID, str]:
    names: dict[UUID, str] = {}

    for item in items:
        product_id = item.product_id

        if product_id not in names:
            names[product_id] = str(
                getattr(
                    item,
                    "product_name",
                    product_id,
                )
            )

    return names


async def _lock_order_products(
    db: AsyncSession,
    *,
    store_id: UUID,
    product_ids: Iterable[UUID],
    require_active: bool,
    load_configuration: bool,
) -> dict[UUID, Product]:
    unique_product_ids = sorted(
        set(product_ids),
        key=str,
    )

    if not unique_product_ids:
        return {}

    query = (
        select(Product)
        .where(
            Product.store_id == store_id,
            Product.id.in_(unique_product_ids),
        )
        .order_by(Product.id)
        .with_for_update()
    )

    if require_active:
        query = query.where(
            Product.is_active.is_(True)
        )

    if load_configuration:
        query = query.options(
            selectinload(
                Product.order_fields
            ).selectinload(
                ProductOrderField.options
            )
        )

    result = await db.execute(query)

    return {
        product.id: product
        for product in (
            result.scalars()
            .unique()
            .all()
        )
    }


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
        normalized_idempotency_key = normalize_order_idempotency_key(
            idempotency_key
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    request_fingerprint = build_order_request_fingerprint(
        payload.model_dump(mode="json")
    )

    store_result = await db.execute(
        select(Store)
        .where(Store.slug == payload.store_slug)
        .with_for_update(read=True)
    )
    store = store_result.scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    store_name = store.name

    await acquire_order_idempotency_lock(
        db,
        store.id,
        normalized_idempotency_key,
    )

    existing_result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.store_id == store.id,
            Order.idempotency_key == normalized_idempotency_key,
        )
    )
    existing_order = existing_result.scalar_one_or_none()
    if existing_order is not None:
        existing_fingerprint = existing_order.request_fingerprint or ""
        if not hmac.compare_digest(
            existing_fingerprint,
            request_fingerprint,
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This Idempotency-Key was already used with "
                    "different order details."
                ),
            )
        if existing_order.whatsapp_handoff_status == "ready":
            setattr(
                existing_order,
                "whatsapp_message",
                build_whatsapp_order_summary(existing_order, store_name),
            )
        return existing_order

    if not is_store_published(store):
        raise HTTPException(status_code=404, detail="Store not found")

    access_error = get_store_access_error(store)
    if access_error:
        raise HTTPException(status_code=403, detail=access_error)

    product_ids = [
        item.product_id
        for item in payload.items
    ]
    products = await _lock_order_products(
        db,
        store_id=store.id,
        product_ids=product_ids,
        require_active=True,
        load_configuration=True,
    )
    missing_product_ids = [
        product_id
        for product_id in dict.fromkeys(
            product_ids
        )
        if product_id not in products
    ]

    if missing_product_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                "Product not available: "
                f"{missing_product_ids[0]}"
            ),
        )

    requested_quantities = (
        _aggregate_product_quantities(
            payload.items
        )
    )

    for product_id, requested_quantity in (
        requested_quantities.items()
    ):
        product = products[product_id]

        if (
            product.stock_quantity is not None
            and requested_quantity
            > product.stock_quantity
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only {product.stock_quantity} "
                    f"left in stock for {product.name}"
                ),
            )

    ordered_unique_product_ids = list(
        dict.fromkeys(product_ids)
    )

    try:
        fulfillment_method = resolve_order_fulfillment_method(
            [
                products[product_id]
                for product_id
                in ordered_unique_product_ids
            ],
            payload.fulfillment_method,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        delivery_address = resolve_order_location(
            fulfillment_method,
            payload.delivery_address,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    prepared_items = []
    subtotal = Decimal("0.00")
    for item in payload.items:
        product = products.get(item.product_id)
        if not product:
            raise HTTPException(
                status_code=400,
                detail=f"Product not available: {item.product_id}",
            )
        try:
            configuration = resolve_order_item_configuration(
                product,
                item.selected_options,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        line_total = configuration.unit_price * item.quantity
        subtotal += line_total
        prepared_items.append(
            {
                "product": product,
                "quantity": item.quantity,
                "unit_price": configuration.unit_price,
                "line_total": line_total,
                "selected_options": configuration.selected_options,
                "configuration_snapshot": configuration.configuration_snapshot,
            }
        )

    wants_whatsapp = payload.handoff_channel == "whatsapp"
    whatsapp_ready = bool(wants_whatsapp and store.whatsapp_number)
    order = Order(
        store_id=store.id,
        order_number=generate_order_number(),
        idempotency_key=normalized_idempotency_key,
        request_fingerprint=request_fingerprint,
        source="whatsapp_checkout" if wants_whatsapp else "web_checkout",
        fulfillment_method=fulfillment_method,
        whatsapp_handoff_status=(
            "ready" if whatsapp_ready else "unavailable" if wants_whatsapp else "not_requested"
        ),
        handoff_metadata=(
            {"channel": "whatsapp"} if wants_whatsapp else {}
        ),
        status="pending",
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        delivery_address=delivery_address,
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
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                product_type=product.product_type,
                unit_price=prepared["unit_price"],
                quantity=prepared["quantity"],
                line_total=prepared["line_total"],
                selected_options=prepared["selected_options"],
                configuration_snapshot=prepared["configuration_snapshot"],
            )
        )

    await db.commit()
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )
    created_order = result.scalar_one()
    if whatsapp_ready:
        setattr(
            created_order,
            "whatsapp_message",
            build_whatsapp_order_summary(created_order, store_name),
        )
    return created_order



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
    ensure_order_status_transition_allowed(
        previous_status,
        new_status,
    )
    should_deduct_inventory = (
        new_status == "paid"
        and not order.inventory_deducted
    )
    should_restore_inventory = (
        new_status == "cancelled"
        and order.inventory_deducted
        and previous_status
        in {"paid", "processing", "completed"}
    )

    inventory_quantities = (
        _aggregate_product_quantities(
            order.items
        )
    )
    inventory_products: dict[
        UUID,
        Product,
    ] = {}

    if (
        should_deduct_inventory
        or should_restore_inventory
    ):
        inventory_products = (
            await _lock_order_products(
                db,
                store_id=store.id,
                product_ids=(
                    inventory_quantities.keys()
                ),
                require_active=False,
                load_configuration=False,
            )
        )
        missing_product_ids = [
            product_id
            for product_id
            in inventory_quantities
            if product_id
            not in inventory_products
        ]

        if missing_product_ids:
            item_names = (
                _first_item_name_by_product(
                    order.items
                )
            )
            missing_id = missing_product_ids[0]
            raise HTTPException(
                status_code=400,
                detail=(
                    "Product not found for order "
                    "item: "
                    f"{item_names.get(missing_id, missing_id)}"
                ),
            )

    if should_deduct_inventory:
        for product_id, requested_quantity in (
            inventory_quantities.items()
        ):
            product = inventory_products[
                product_id
            ]

            if (
                product.stock_quantity is not None
                and product.stock_quantity
                < requested_quantity
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Not enough stock for "
                        f"{product.name}. Available: "
                        f"{product.stock_quantity}"
                    ),
                )

        for product_id, requested_quantity in (
            inventory_quantities.items()
        ):
            product = inventory_products[
                product_id
            ]

            if product.stock_quantity is not None:
                product.stock_quantity -= (
                    requested_quantity
                )

        order.inventory_deducted = True

    if should_restore_inventory:
        for product_id, restored_quantity in (
            inventory_quantities.items()
        ):
            product = inventory_products[
                product_id
            ]

            if product.stock_quantity is not None:
                product.stock_quantity += (
                    restored_quantity
                )

        order.inventory_deducted = False

    order.status = new_status

    if (
        new_status == "paid"
        and not order.payment_method
    ):
        order.payment_method = "manual"

    await db.commit()
    await db.refresh(order)

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )

    return result.scalar_one()
