from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_store_owner
from app.db.session import get_db
from app.models import Store, Product, Order, OrderItem
from app.schemas.order import PublicOrderCreate, OrderResponse, OrderStatusUpdate
from app.services.subscription import get_store_access_error


router = APIRouter(tags=["orders"])


def generate_order_number() -> str:
    return f"ORD-{uuid4().hex[:10].upper()}"


@router.post("/public/orders", response_model=OrderResponse)
async def create_public_order(payload: PublicOrderCreate, db: AsyncSession = Depends(get_db)):
    store_result = await db.execute(
        select(Store).where(Store.slug == payload.store_slug)
    )
    store = store_result.scalar_one_or_none()

    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    access_error = get_store_access_error(store)

    if access_error:
        raise HTTPException(status_code=403, detail=access_error)

    product_ids = [item.product_id for item in payload.items]

    products_result = await db.execute(
        select(Product).where(
            Product.store_id == store.id,
            Product.id.in_(product_ids),
            Product.is_active == True,
        )
    )

    products = {product.id: product for product in products_result.scalars().all()}

    prepared_items = []
    subtotal = Decimal("0.00")

    for item in payload.items:
        product = products.get(item.product_id)

        if not product:
            raise HTTPException(status_code=400, detail=f"Product not available: {item.product_id}")

        if product.stock_quantity is not None and item.quantity > product.stock_quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Only {product.stock_quantity} left in stock for {product.name}",
            )

        line_total = product.price * item.quantity
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
        status="pending",
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=payload.customer_email,
        delivery_address=payload.delivery_address,
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
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )

    return result.scalar_one()



@router.get("/public/orders/{order_number}", response_model=OrderResponse)
async def get_public_order_status(
    order_number: str,
    customer_phone: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order, Store.slug)
        .join(Store, Store.id == Order.store_id)
        .options(selectinload(Order.items))
        .where(
            Order.order_number == order_number,
            Order.customer_phone == customer_phone,
        )
    )

    row = result.first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Order not found. Please check your order number and phone number.",
        )

    order, store_slug = row
    setattr(order, "store_slug", store_slug)

    return order

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
    should_deduct_inventory = new_status == "paid" and not order.inventory_deducted

    order.status = new_status

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

    await db.commit()
    await db.refresh(order)

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
    )

    return result.scalar_one()
