import asyncio
import logging
import math
import time
from collections import OrderedDict
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from redis.asyncio import Redis

from app.core.config import settings


logger = logging.getLogger(__name__)

_FALLBACK_MAX_BUCKETS = 10_000
_FALLBACK_LOG_INTERVAL_SECONDS = 60

_REDIS_RATE_LIMIT_SCRIPT = """
local attempts = redis.call("INCR", KEYS[1])
local ttl = redis.call("TTL", KEYS[1])

if attempts == 1 or ttl < 0 then
    redis.call("EXPIRE", KEYS[1], tonumber(ARGV[1]))
    ttl = tonumber(ARGV[1])
end

return {attempts, ttl}
"""


@dataclass
class _FallbackBucket:
    attempts: int
    expires_at: float


_fallback_buckets: OrderedDict[
    str,
    _FallbackBucket,
] = OrderedDict()

_fallback_lock = asyncio.Lock()
_fallback_log_lock = asyncio.Lock()
_last_fallback_log_at = 0.0


def _rate_limit_key(
    store_id: UUID,
) -> str:
    return (
        "rate-limit:image-upload:"
        f"{store_id}"
    )


def _redis_client() -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


def _raise_rate_limit_error(
    wait_seconds: int,
) -> None:
    safe_wait_seconds = max(
        wait_seconds,
        1,
    )

    raise HTTPException(
        status_code=429,
        detail=(
            "Too many image uploads. "
            "Try again shortly."
        ),
        headers={
            "Retry-After": str(
                safe_wait_seconds
            ),
        },
    )


async def _log_fallback_mode() -> None:
    global _last_fallback_log_at

    now = time.monotonic()

    async with _fallback_log_lock:
        if (
            now - _last_fallback_log_at
            < _FALLBACK_LOG_INTERVAL_SECONDS
        ):
            return

        _last_fallback_log_at = now

        logger.critical(
            "Redis is unavailable for image "
            "upload rate limiting. Using "
            "bounded in-process fallback."
        )


async def _enforce_fallback_limit(
    key: str,
) -> None:
    now = time.monotonic()
    window_seconds = (
        settings
        .IMAGE_UPLOAD_RATE_LIMIT_WINDOW_SECONDS
    )
    attempt_limit = (
        settings
        .IMAGE_UPLOAD_RATE_LIMIT_ATTEMPTS
    )

    async with _fallback_lock:
        expired_keys = [
            bucket_key
            for bucket_key, bucket
            in _fallback_buckets.items()
            if bucket.expires_at <= now
        ]

        for expired_key in expired_keys:
            _fallback_buckets.pop(
                expired_key,
                None,
            )

        bucket = (
            _fallback_buckets.get(key)
        )

        if bucket is None:
            bucket = _FallbackBucket(
                attempts=1,
                expires_at=(
                    now + window_seconds
                ),
            )
            _fallback_buckets[key] = (
                bucket
            )
        else:
            bucket.attempts += 1
            _fallback_buckets.move_to_end(
                key
            )

        while (
            len(_fallback_buckets)
            > _FALLBACK_MAX_BUCKETS
        ):
            _fallback_buckets.popitem(
                last=False
            )

        if (
            bucket.attempts
            > attempt_limit
        ):
            wait_seconds = math.ceil(
                bucket.expires_at - now
            )

            _raise_rate_limit_error(
                wait_seconds
            )


async def enforce_image_upload_rate_limit(
    store_id: UUID,
) -> None:
    key = _rate_limit_key(
        store_id
    )
    redis: Redis | None = None

    try:
        redis = _redis_client()

        result = await redis.eval(
            _REDIS_RATE_LIMIT_SCRIPT,
            1,
            key,
            settings
            .IMAGE_UPLOAD_RATE_LIMIT_WINDOW_SECONDS,
        )

        attempts = int(result[0])
        ttl = int(result[1])

        if (
            attempts
            > settings
            .IMAGE_UPLOAD_RATE_LIMIT_ATTEMPTS
        ):
            _raise_rate_limit_error(
                ttl
            )
    except HTTPException:
        raise
    except Exception:
        await _log_fallback_mode()
        await _enforce_fallback_limit(
            key
        )
    finally:
        if redis is not None:
            await redis.aclose()
