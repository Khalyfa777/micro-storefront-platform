import hashlib
import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)


_IDEMPOTENCY_KEY_PATTERN = re.compile(
    r"^[A-Za-z0-9]"
    r"[A-Za-z0-9._:-]{15,127}$"
)


def normalize_order_idempotency_key(
    value: str | None,
) -> str:
    if value is None:
        raise ValueError(
            "Idempotency-Key header is required."
        )

    normalized = value.strip()

    if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(
        normalized
    ):
        raise ValueError(
            "Idempotency-Key must contain "
            "16 to 128 letters, numbers, "
            "periods, underscores, colons, "
            "or hyphens."
        )

    return normalized


def build_order_request_fingerprint(
    payload: dict[str, Any],
) -> str:
    canonical_payload = dict(payload)

    items = canonical_payload.get("items")

    if isinstance(items, list):
        canonical_payload["items"] = sorted(
            (
                dict(item)
                for item in items
            ),
            key=lambda item: (
                str(
                    item.get(
                        "product_id",
                        "",
                    )
                ),
                int(
                    item.get(
                        "quantity",
                        0,
                    )
                ),
            ),
        )

    encoded = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


async def acquire_order_idempotency_lock(
    db: AsyncSession,
    store_id: UUID | str,
    idempotency_key: str,
) -> None:
    lock_material = (
        "public-order:"
        f"{store_id}:"
        f"{idempotency_key}"
    )

    statement = text(
        """
        SELECT pg_advisory_xact_lock(
            hashtextextended(
                :lock_material,
                0
            )
        )
        """
    ).bindparams(
        lock_material=lock_material
    )

    await db.execute(statement)
