import hashlib
import logging

from fastapi import HTTPException, Request
from redis.asyncio import Redis

from app.core.config import settings


logger = logging.getLogger(__name__)

LOGIN_LIMIT = 5
LOGIN_WINDOW_SECONDS = 300

_LOGIN_ATTEMPT_SCRIPT = """
local attempts = redis.call("INCR", KEYS[1])
local ttl = redis.call("TTL", KEYS[1])

if attempts == 1 or ttl < 0 then
    redis.call("EXPIRE", KEYS[1], tonumber(ARGV[1]))
    ttl = tonumber(ARGV[1])
end

return {attempts, ttl}
"""


def _client_ip(request: Request) -> str:
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get(
            "x-forwarded-for"
        )

        if forwarded_for:
            forwarded_ip = forwarded_for.split(",")[0].strip()

            if forwarded_ip:
                return forwarded_ip

    if request.client:
        return request.client.host

    return "unknown"


def _email_hash(email: str) -> str:
    normalized = email.strip().lower()

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


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
    return (
        "rate-limit:login:"
        f"{_client_ip(request)}:"
        f"{_email_hash(email)}"
    )


async def enforce_login_rate_limit(
    request: Request,
    email: str,
) -> None:
    key = _rate_limit_key(request, email)
    redis = _redis_client()

    try:
        result = await redis.eval(
            _LOGIN_ATTEMPT_SCRIPT,
            1,
            key,
            LOGIN_WINDOW_SECONDS,
        )

        attempts = int(result[0])
        ttl = int(result[1])

        if attempts > LOGIN_LIMIT:
            wait_seconds = max(ttl, 1)

            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many login attempts. "
                    f"Try again in {wait_seconds} seconds."
                ),
                headers={
                    "Retry-After": str(wait_seconds),
                },
            )
    except HTTPException:
        raise
    except Exception:
        # Preserve dashboard availability during a Redis outage.
        # No email address, token, or IP address is logged.
        logger.error(
            "Login rate limiter is unavailable; "
            "allowing the authentication attempt.",
            exc_info=True,
        )
    finally:
        await redis.aclose()


async def clear_login_rate_limit(
    request: Request,
    email: str,
) -> None:
    key = _rate_limit_key(request, email)
    redis = _redis_client()

    try:
        await redis.delete(key)
    except Exception:
        logger.warning(
            "Unable to clear the login rate-limit bucket.",
            exc_info=True,
        )
    finally:
        await redis.aclose()
