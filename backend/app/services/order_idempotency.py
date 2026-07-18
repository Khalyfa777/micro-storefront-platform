
import hashlib
import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")


def normalize_order_idempotency_key(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("Idempotency-Key header is required.")
    if not _IDEMPOTENCY_KEY_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Idempotency-Key must be 16 to 128 characters and use only "
            "letters, numbers, periods, underscores, colons, or hyphens."
        )
    return normalized


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(
                value.items(),
                key=lambda entry: str(entry[0]),
            )
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    return value


def _canonical_item_sort_key(
    item: Any,
) -> tuple[str, str]:
    if not isinstance(item, dict):
        return "", json.dumps(
            item,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    return (
        str(item.get("product_id", "")),
        json.dumps(
            item,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ),
    )


def build_order_request_fingerprint(payload: dict[str, Any]) -> str:
    canonical_payload = _canonicalize(payload)
    items = canonical_payload.get("items")

    if isinstance(items, list):
        canonical_payload["items"] = sorted(
            items,
            key=_canonical_item_sort_key,
        )
    encoded = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def acquire_order_idempotency_lock(
    db: AsyncSession,
    store_id: UUID,
    idempotency_key: str,
) -> None:
    await db.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            "hashtextextended(:lock_identity, 0)"
            ")"
        ),
        {
            "lock_identity": (
                f"public-order:{store_id}:{idempotency_key}"
            )
        },
    )
