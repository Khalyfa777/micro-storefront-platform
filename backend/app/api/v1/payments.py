import hashlib
import hmac
import os
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.config import settings
from app.models import Order, Product, Transaction, Store
from app.schemas.payment import PaymentInitializeRequest, PaymentInitializeResponse
from app.services.plan_features import ensure_plan_allows_online_payments


router = APIRouter(prefix="/payments", tags=["payments"])


def generate_reference() -> str:
    return f"MSF-{uuid4().hex[:16].upper()}"


def get_paystack_secret_key() -> str:
    if not settings.PAYSTACK_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="PAYSTACK_SECRET_KEY is not configured",
        )

    return settings.PAYSTACK_SECRET_KEY


async def mark_order_paid_and_deduct_inventory(
    db: AsyncSession,
    order: Order,
    transaction: Transaction,
    raw_response: dict,
):
    """
    Payment-safe inventory deduction.

    This function re-locks the order row before checking inventory_deducted.
    That prevents Paystack webhook + redirect verification from deducting stock twice.
    """
    locked_order_result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    locked_order = locked_order_result.scalar_one_or_none()

    if not locked_order:
        raise HTTPException(status_code=404, detail="Order not found")

    locked_transaction_result = await db.execute(
        select(Transaction)
        .where(Transaction.id == transaction.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    locked_transaction = locked_transaction_result.scalar_one_or_none()

    if not locked_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    locked_transaction.raw_response = raw_response
    locked_transaction.status = "success"

    if not locked_transaction.verified_at:
        locked_transaction.verified_at = datetime.now(timezone.utc)

    locked_order.status = "paid"

    if not locked_order.inventory_deducted:
        product_ids = [item.product_id for item in locked_order.items]

        product_result = await db.execute(
            select(Product)
            .where(Product.id.in_(product_ids))
            .with_for_update()
            .execution_options(populate_existing=True)
        )

        products_by_id = {
            product.id: product
            for product in product_result.scalars().all()
        }

        for item in locked_order.items:
            product = products_by_id.get(item.product_id)

            if not product or product.stock_quantity is None:
                continue

            if product.stock_quantity < item.quantity:
                # Payment has already succeeded, so do not fail the payment confirmation.
                # Flag the order so the merchant knows stock was oversold.
                locked_order.is_oversold = True
                product.stock_quantity = 0
            else:
                product.stock_quantity -= item.quantity

        locked_order.inventory_deducted = True

    await db.commit()
    await db.refresh(locked_order)

    return locked_order

@router.post("/initialize", response_model=PaymentInitializeResponse)
async def initialize_payment(
    payload: PaymentInitializeRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == payload.order_id)
            .with_for_update()
    )

    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in ["pending"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot initialize payment for order with status {order.status}",
        )

    store_result = await db.execute(
        select(Store).where(Store.id == order.store_id)
    )
    store = store_result.scalar_one_or_none()

    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    await ensure_plan_allows_online_payments(db, store)

    paystack_secret_key = get_paystack_secret_key()
    existing_result = await db.execute(
        select(Transaction).where(
            Transaction.order_id == order.id,
            Transaction.status == "pending",
        )
    )
    existing_transaction = existing_result.scalar_one_or_none()

    if existing_transaction and existing_transaction.authorization_url:
        return PaymentInitializeResponse(
            authorization_url=existing_transaction.authorization_url,
            access_code=existing_transaction.access_code or "",
            reference=existing_transaction.provider_reference,
        )

    reference = generate_reference()
    email = payload.customer_email or order.customer_email or "customer@example.com"
    amount_kobo = int(order.total * 100)

    paystack_payload = {
        "email": email,
        "amount": amount_kobo,
        "currency": order.currency,
        "reference": reference,
        "callback_url": f"{settings.FRONTEND_URL.rstrip('/')}/payment/processing",
        "metadata": {
            "order_id": str(order.id),
            "store_id": str(order.store_id),
            "order_number": order.order_number,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.paystack.co/transaction/initialize",
            headers={
                "Authorization": f"Bearer {paystack_secret_key}",
                "Content-Type": "application/json",
            },
            json=paystack_payload,
        )

    data = response.json()

    if response.status_code >= 400 or not data.get("status"):
        raise HTTPException(
            status_code=400,
            detail=data.get("message", "Could not initialize payment"),
        )

    paystack_data = data["data"]

    transaction = Transaction(
        order_id=order.id,
        store_id=order.store_id,
        provider_reference=reference,
        amount=order.total,
        currency=order.currency,
        status="pending",
        authorization_url=paystack_data["authorization_url"],
        access_code=paystack_data["access_code"],
        raw_response=data,
    )

    db.add(transaction)
    await db.commit()

    return PaymentInitializeResponse(
        authorization_url=paystack_data["authorization_url"],
        access_code=paystack_data["access_code"],
        reference=reference,
    )


@router.get("/verify/{reference}")
async def verify_payment(reference: str, db: AsyncSession = Depends(get_db)):
    paystack_secret_key = get_paystack_secret_key()

    tx_result = await db.execute(
        select(Transaction).where(Transaction.provider_reference == reference)
    )
    transaction = tx_result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    order_result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == transaction.order_id)
    )
    order = order_result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={
                "Authorization": f"Bearer {paystack_secret_key}",
            },
        )

    data = response.json()

    if response.status_code >= 400 or not data.get("status"):
        raise HTTPException(
            status_code=400,
            detail=data.get("message", "Could not verify payment"),
        )

    paystack_data = data["data"]
    paystack_status = paystack_data.get("status")
    paid_amount_kobo = paystack_data.get("amount")
    expected_amount_kobo = int(order.total * 100)

    if paystack_status == "success" and paid_amount_kobo == expected_amount_kobo:
        order = await mark_order_paid_and_deduct_inventory(
            db=db,
            order=order,
            transaction=transaction,
            raw_response=data,
        )

        return {
            "status": "success",
            "message": "Payment verified successfully",
            "order_id": str(order.id),
            "order_number": order.order_number,
            "order_status": order.status,
            "inventory_deducted": order.inventory_deducted,
            "amount": str(order.total),
            "currency": order.currency,
        }

    transaction.raw_response = data
    transaction.status = paystack_status or "failed"
    await db.commit()

    return {
        "status": transaction.status,
        "message": "Payment was not successful",
        "order_id": str(order.id),
        "order_number": order.order_number,
        "order_status": order.status,
        "inventory_deducted": order.inventory_deducted,
    }


@router.post("/webhook")
async def paystack_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    paystack_secret_key = get_paystack_secret_key()

    raw_body = await request.body()
    paystack_signature = request.headers.get("x-paystack-signature")

    if not paystack_signature:
        raise HTTPException(status_code=401, detail="Missing Paystack signature")

    computed_signature = hmac.new(
        paystack_secret_key.encode("utf-8"),
        raw_body,
        hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(computed_signature, paystack_signature):
        raise HTTPException(status_code=401, detail="Invalid Paystack signature")

    payload = await request.json()

    event = payload.get("event")
    data = payload.get("data", {})

    if event != "charge.success":
        return {
            "status": "ignored",
            "message": f"Ignored event {event}",
        }

    reference = data.get("reference")
    paid_amount_kobo = data.get("amount")
    paystack_status = data.get("status")

    if not reference:
        raise HTTPException(status_code=400, detail="Missing transaction reference")

    tx_result = await db.execute(
        select(Transaction).where(Transaction.provider_reference == reference)
    )
    transaction = tx_result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    order_result = await db.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == transaction.order_id)
    )
    order = order_result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    expected_amount_kobo = int(order.total * 100)

    if paystack_status == "success" and paid_amount_kobo == expected_amount_kobo:
        order = await mark_order_paid_and_deduct_inventory(
            db=db,
            order=order,
            transaction=transaction,
            raw_response=payload,
        )

        return {
            "status": "success",
            "message": "Webhook processed successfully",
            "order_number": order.order_number,
            "order_status": order.status,
            "inventory_deducted": order.inventory_deducted,
        }

    transaction.raw_response = payload
    transaction.status = paystack_status or "failed"
    await db.commit()

    return {
        "status": "failed",
        "message": "Payment amount/status did not match",
        "order_number": order.order_number,
        "order_status": order.status,
        "inventory_deducted": order.inventory_deducted,
    }
