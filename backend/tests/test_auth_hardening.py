from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request

from app.api.v1 import auth
from app.core.security import verify_password
from app.schemas.auth import LoginRequest
from app.services import auth_rate_limit


class BrokenRedis:
    async def eval(self, *args, **kwargs):
        raise ConnectionError(
            "Controlled Redis outage."
        )

    async def delete(self, *args, **kwargs):
        raise ConnectionError(
            "Controlled Redis outage."
        )

    async def aclose(self):
        return None


class FakeResult:
    def __init__(self, user):
        self.user = user

    def scalar_one_or_none(self):
        return self.user


class FakeSession:
    def __init__(self, user):
        self.user = user

    async def execute(self, statement):
        return FakeResult(self.user)


def make_request(
    client_ip: str = "203.0.113.10",
) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/api/v1/auth/login",
            "raw_path": b"/api/v1/auth/login",
            "query_string": b"",
            "headers": [],
            "client": (
                client_ip,
                50000,
            ),
            "server": (
                "api.storeplughq.com",
                443,
            ),
        }
    )


def test_dummy_login_hash_is_valid() -> None:
    result = verify_password(
        "controlled-invalid-password",
        auth.DUMMY_LOGIN_PASSWORD_HASH,
    )

    assert result is False


def test_login_rate_limit_key_hides_identifiers() -> None:
    request = make_request(
        "203.0.113.55"
    )

    key = auth_rate_limit._rate_limit_key(
        request,
        "Seller@Example.com",
    )

    assert "203.0.113.55" not in key
    assert "seller@example.com" not in key
    assert "Seller@Example.com" not in key
    assert key.startswith(
        "rate-limit:login:"
    )


@pytest.mark.asyncio
async def test_redis_outage_fallback_blocks_and_clears(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        auth_rate_limit,
        "_redis_client",
        lambda: BrokenRedis(),
    )

    auth_rate_limit._fallback_buckets.clear()
    auth_rate_limit._last_fallback_log_at = 0.0

    request = make_request()
    email = "fallback-test@example.com"

    for _ in range(
        auth_rate_limit.LOGIN_LIMIT
    ):
        await auth_rate_limit\
            .enforce_login_rate_limit(
                request,
                email,
            )

    with pytest.raises(
        HTTPException
    ) as error:
        await auth_rate_limit\
            .enforce_login_rate_limit(
                request,
                email,
            )

    assert error.value.status_code == 429
    assert (
        error.value.headers[
            "Retry-After"
        ]
    )

    await auth_rate_limit\
        .clear_login_rate_limit(
            request,
            email,
        )

    await auth_rate_limit\
        .enforce_login_rate_limit(
            request,
            email,
        )

    auth_rate_limit._fallback_buckets.clear()


@pytest.mark.asyncio
async def test_unknown_account_uses_dummy_hash(
    monkeypatch,
) -> None:
    verification_calls = []

    async def no_rate_limit(
        request,
        email,
    ):
        return None

    def controlled_verify(
        password,
        password_hash,
    ):
        verification_calls.append(
            (
                password,
                password_hash,
            )
        )

        return False

    monkeypatch.setattr(
        auth,
        "enforce_login_rate_limit",
        no_rate_limit,
    )

    monkeypatch.setattr(
        auth,
        "verify_password",
        controlled_verify,
    )

    payload = LoginRequest(
        email="missing@example.com",
        password="WrongPass123!",
    )

    with pytest.raises(
        HTTPException
    ) as error:
        await auth.login(
            make_request(),
            payload,
            FakeSession(None),
        )

    assert error.value.status_code == 401

    assert verification_calls == [
        (
            "WrongPass123!",
            auth.DUMMY_LOGIN_PASSWORD_HASH,
        )
    ]


@pytest.mark.asyncio
async def test_invited_account_without_password_uses_dummy_hash(
    monkeypatch,
) -> None:
    verification_calls = []

    async def no_rate_limit(
        request,
        email,
    ):
        return None

    def controlled_verify(
        password,
        password_hash,
    ):
        verification_calls.append(
            password_hash
        )

        return False

    monkeypatch.setattr(
        auth,
        "enforce_login_rate_limit",
        no_rate_limit,
    )

    monkeypatch.setattr(
        auth,
        "verify_password",
        controlled_verify,
    )

    invited_user = SimpleNamespace(
        password_hash=None,
    )

    payload = LoginRequest(
        email="invited@example.com",
        password="WrongPass123!",
    )

    with pytest.raises(
        HTTPException
    ) as error:
        await auth.login(
            make_request(),
            payload,
            FakeSession(invited_user),
        )

    assert error.value.status_code == 401

    assert verification_calls == [
        auth.DUMMY_LOGIN_PASSWORD_HASH
    ]


@pytest.mark.asyncio
async def test_existing_account_uses_stored_hash(
    monkeypatch,
) -> None:
    verification_calls = []

    async def no_rate_limit(
        request,
        email,
    ):
        return None

    def controlled_verify(
        password,
        password_hash,
    ):
        verification_calls.append(
            password_hash
        )

        return False

    monkeypatch.setattr(
        auth,
        "enforce_login_rate_limit",
        no_rate_limit,
    )

    monkeypatch.setattr(
        auth,
        "verify_password",
        controlled_verify,
    )

    existing_user = SimpleNamespace(
        password_hash="stored-password-hash",
    )

    payload = LoginRequest(
        email="existing@example.com",
        password="WrongPass123!",
    )

    with pytest.raises(
        HTTPException
    ) as error:
        await auth.login(
            make_request(),
            payload,
            FakeSession(existing_user),
        )

    assert error.value.status_code == 401

    assert verification_calls == [
        "stored-password-hash"
    ]
