import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from app.core.config import settings


INVITATION_TOKEN_BYTES = 32


def generate_invitation_token() -> str:
    return secrets.token_urlsafe(INVITATION_TOKEN_BYTES)


def hash_invitation_token(raw_token: str) -> str:
    token = raw_token.strip()

    if not token:
        raise ValueError("Invitation token cannot be empty.")

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def get_invitation_expiry(
    now: datetime | None = None,
) -> datetime:
    current_time = now or datetime.now(timezone.utc)

    if current_time.tzinfo is None:
        current_time = current_time.replace(
            tzinfo=timezone.utc
        )

    return current_time + timedelta(
        hours=settings.SELLER_INVITATION_EXPIRE_HOURS
    )


def build_invitation_url(raw_token: str) -> str:
    token = raw_token.strip()

    if not token:
        raise ValueError("Invitation token cannot be empty.")

    dashboard_url = settings.DASHBOARD_PUBLIC_URL.rstrip("/")
    encoded_token = quote(token, safe="")

    return (
        f"{dashboard_url}/accept-invite"
        f"#token={encoded_token}"
    )
