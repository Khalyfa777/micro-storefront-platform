from datetime import (
    datetime,
    timedelta,
    timezone,
)

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_token,
)


def test_access_token_round_trip_with_pyjwt():
    token = create_access_token(
        subject="jwt-test-user",
        role="admin",
    )

    payload = decode_token(token)

    assert payload["sub"] == "jwt-test-user"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_invalid_token_is_mapped_to_value_error():
    with pytest.raises(
        ValueError,
        match="Invalid token",
    ):
        decode_token(
            "this-is-not-a-valid-token"
        )


def test_expired_token_is_rejected():
    payload = {
        "sub": "expired-user",
        "role": "seller",
        "type": "access",
        "exp": (
            datetime.now(timezone.utc)
            - timedelta(minutes=1)
        ),
    }

    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(
        ValueError,
        match="Invalid token",
    ):
        decode_token(token)
