import hashlib

from fastapi import HTTPException, Request
from redis.asyncio import Redis

from app.core.config import settings


LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 300


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"


def _email_hash(email: str) -> str:
    normalized = email.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _redis_client() -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )


async def enforce_login_rate_limit(request: Request, email: str) -> None:
    ip = _client_ip(request)
    key = f"rate-limit:login:{ip}:{_email_hash(email)}"

    redis = _redis_client()

    try:
        attempts = await redis.incr(key)

        if attempts == 1:
            await redis.expire(key, LOGIN_WINDOW_SECONDS)

        ttl = await redis.ttl(key)

        if attempts > LOGIN_LIMIT:
            wait_seconds = max(ttl, 60)
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Try again in {wait_seconds} seconds.",
            )
    except HTTPException:
        raise
    except Exception:
        # Fail open so Redis outage does not lock out all merchants.
        return
    finally:
        await redis.aclose()


async def clear_login_rate_limit(request: Request, email: str) -> None:
    ip = _client_ip(request)
    key = f"rate-limit:login:{ip}:{_email_hash(email)}"

    redis = _redis_client()

    try:
        await redis.delete(key)
    except Exception:
        return
    finally:
        await redis.aclose()