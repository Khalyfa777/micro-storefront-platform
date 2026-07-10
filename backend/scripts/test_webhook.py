import asyncio
import hashlib
import hmac
import json
import os

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    secret = os.getenv("PAYSTACK_SECRET_KEY")
    database_url = os.getenv("DATABASE_URL")

    if not secret:
        raise RuntimeError("PAYSTACK_SECRET_KEY is missing")

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")

    engine = create_async_engine(database_url)

    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT
                    t.provider_reference,
                    t.status AS transaction_status,
                    o.id AS order_id,
                    o.store_id,
                    o.order_number,
                    o.total,
                    o.status AS order_status
                FROM transactions t
                JOIN orders o ON o.id = t.order_id
                ORDER BY t.created_at DESC
                LIMIT 1
            """)
        )

        row = result.mappings().first()

    await engine.dispose()

    if not row:
        raise RuntimeError("No transaction found. Create an order and click Pay now first.")

    amount_kobo = int(float(row["total"]) * 100)

    payload = {
        "event": "charge.success",
        "data": {
            "reference": row["provider_reference"],
            "status": "success",
            "amount": amount_kobo,
            "currency": "GHS",
            "metadata": {
                "order_id": str(row["order_id"]),
                "store_id": str(row["store_id"]),
                "order_number": row["order_number"],
            },
        },
    }

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    signature = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha512,
    ).hexdigest()

    print("Testing webhook with:")
    print("Reference:", row["provider_reference"])
    print("Order:", row["order_number"])
    print("Amount kobo:", amount_kobo)
    print()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "http://localhost:8000/api/v1/payments/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "x-paystack-signature": signature,
            },
        )

    print("Webhook status code:", response.status_code)
    print("Webhook response:")
    print(response.text)


asyncio.run(main())
