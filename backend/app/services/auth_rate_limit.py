import asyncio
import hashlib
import logging
import math
import time
from collections import OrderedDict
from dataclasses import dataclass

from fastapi import HTTPException, Request
from redis.asyncio import Redis

from app.core.config import settings


logger = logging.getLogger(__name__)

LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 300

FALLBACK_MAX_BUCKETS = 10_000
FALLBACK_LOG_INTERVAL_SECONDS = 60

_LOGIN_ATTEMPT_SCRIPT = """
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


def _client_ip(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get(
            "x-forwarded-for"
        )

        if forwarded_for:
            forwarded_ip = (
                forwarded_for
                .split(",")[0]
                .strip()
            )

            if forwarded_ip:
                return forwarded_ip

    if request.client:
        return request.client.host

    return "unknown"


def _identifier_hash(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _email_hash(email: str) -> str:
    normalized = email.strip().lower()

    return _identifier_hash(normalized)


def _redis_client() -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


def _rate_limit_key(
    request: Request,
    email: str,
) -> str:
    client_hash = _identifier_hash(
        _client_ip(request)
    )

    return (
        "rate-limit:login:"
        f"{client_hash}:"
        f"{_email_hash(email)}"
    )


def _raise_login_rate_limit_error(
    wait_seconds: int,
) -> None:
    safe_wait_seconds = max(
        wait_seconds,
        1,
    )

    raise HTTPException(
        status_code=429,
        detail=(
            "Too many login attempts. "
            f"Try again in "
            f"{safe_wait_seconds} seconds."
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
            < FALLBACK_LOG_INTERVAL_SECONDS
        ):
            return

        _last_fallback_log_at = now

        logger.critical(
            "Redis is unavailable for login "
            "rate limiting. Using bounded "
            "in-process fallback."
        )


async def _enforce_fallback_limit(
    key: str,
) -> None:
    now = time.monotonic()

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

        bucket = _fallback_buckets.get(key)

        if bucket is None:
            bucket = _FallbackBucket(
                attempts=1,
                expires_at=(
                    now + LOGIN_WINDOW_SECONDS
                ),
            )

            _fallback_buckets[key] = bucket
        else:
            bucket.attempts += 1
            _fallback_buckets.move_to_end(
                key
            )

        while (
            len(_fallback_buckets)
            > FALLBACK_MAX_BUCKETS
        ):
            _fallback_buckets.popitem(
                last=False
            )

        if bucket.attempts > LOGIN_LIMIT:
            wait_seconds = math.ceil(
                bucket.expires_at - now
            )

            _raise_login_rate_limit_error(
                wait_seconds
            )


async def _clear_fallback_limit(
    key: str,
) -> None:
    async with _fallback_lock:
        _fallback_buckets.pop(
            key,
            None,
        )


async def enforce_login_rate_limit(
    request: Request,
    email: str,
) -> None:
    key = _rate_limit_key(
        request,
        email,
    )

    redis: Redis | None = None

    try:
        redis = _redis_client()

        result = await redis.eval(
            _LOGIN_ATTEMPT_SCRIPT,
            1,
            key,
            LOGIN_WINDOW_SECONDS,
        )

        attempts = int(result[0])
        ttl = int(result[1])

        if attempts > LOGIN_LIMIT:
            _raise_login_rate_limit_error(
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


async def clear_login_rate_limit(
    request: Request,
    email: str,
) -> None:
    key = _rate_limit_key(
        request,
        email,
    )

    redis: Redis | None = None

    try:
        redis = _redis_client()
        await redis.delete(key)

    except Exception:
        await _log_fallback_mode()

    finally:
        if redis is not None:
            await redis.aclose()

    await _clear_fallback_limit(key)
