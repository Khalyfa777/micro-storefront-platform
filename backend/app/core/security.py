from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    password: str,
    hashed: str,
) -> bool:
    return pwd_context.verify(
        password,
        hashed,
    )


def create_access_token(
    subject: str,
    role: str,
    token_version: int = 0,
) -> str:
    if (
        isinstance(token_version, bool)
        or not isinstance(token_version, int)
        or token_version < 0
    ):
        raise ValueError(
            "Token version must be a non-negative integer."
        )

    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=(
                settings
                .JWT_ACCESS_EXPIRE_MINUTES
            )
        )
    )

    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "ver": token_version,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[
                settings.JWT_ALGORITHM,
            ],
        )
    except InvalidTokenError as exc:
        raise ValueError(
            "Invalid token"
        ) from exc
