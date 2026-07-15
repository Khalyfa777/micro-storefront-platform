import asyncio
import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import (
    HTTPAuthorizationCredentials,
)

from app.api import deps
from app.api.v1 import auth
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_token,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
)


OLD_PASSWORD = "OldPass123!"
NEW_PASSWORD = "NewPass456!"
SECOND_NEW_PASSWORD = "OtherPass789!"


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class ReadSession:
    def __init__(self, user):
        self.user = user

    async def execute(self, statement):
        return ScalarResult(self.user)


class LockedSession:
    def __init__(self, shared_user):
        self.shared_user = shared_user
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        return ScalarResult(
            self.shared_user
        )

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class SharedCredentialState:
    def __init__(
        self,
        user_id,
        password_hash,
        token_version,
    ):
        self.user = SimpleNamespace(
            id=user_id,
            email="security@example.com",
            password_hash=password_hash,
            token_version=token_version,
            role="merchant",
            is_active=True,
            is_verified=True,
        )
        self.lock = asyncio.Lock()


class ConcurrentLockedSession:
    def __init__(
        self,
        state: SharedCredentialState,
    ):
        self.state = state
        self.locked = False
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, statement):
        await self.state.lock.acquire()
        self.locked = True

        return ScalarResult(
            self.state.user
        )

    async def commit(self):
        self.commits += 1
        self._release()

    async def rollback(self):
        self.rollbacks += 1
        self._release()

    def _release(self):
        if self.locked:
            self.locked = False
            self.state.lock.release()


def credentials(token: str):
    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )


def make_user(
    *,
    token_version: int = 0,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="security@example.com",
        password_hash=(
            f"hash:{OLD_PASSWORD}"
        ),
        token_version=token_version,
        role="merchant",
        is_active=True,
        is_verified=True,
    )


async def immediate_threadpool(
    function,
    *args,
):
    return function(*args)


def fake_verify_password(
    password,
    password_hash,
):
    return (
        password_hash
        == f"hash:{password}"
    )


def fake_hash_password(password):
    return f"hash:{password}"


def install_fast_password_functions(
    monkeypatch,
):
    monkeypatch.setattr(
        auth,
        "run_in_threadpool",
        immediate_threadpool,
    )
    monkeypatch.setattr(
        auth,
        "verify_password",
        fake_verify_password,
    )
    monkeypatch.setattr(
        auth,
        "hash_password",
        fake_hash_password,
    )


def make_unversioned_token(
    user_id,
):
    payload = {
        "sub": str(user_id),
        "role": "merchant",
        "type": "access",
        "exp": (
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        ),
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


@pytest.mark.asyncio
async def test_unversioned_legacy_token_is_rejected():
    user = make_user()

    with pytest.raises(
        HTTPException
    ) as error:
        await deps.get_current_user(
            credentials(
                make_unversioned_token(
                    user.id
                )
            ),
            ReadSession(user),
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid token."


@pytest.mark.asyncio
async def test_mismatched_token_version_is_rejected():
    user = make_user(
        token_version=2
    )
    token = create_access_token(
        str(user.id),
        user.role,
        token_version=1,
    )

    with pytest.raises(
        HTTPException
    ) as error:
        await deps.get_current_user(
            credentials(token),
            ReadSession(user),
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid token."


@pytest.mark.asyncio
async def test_matching_token_version_is_accepted():
    user = make_user(
        token_version=3
    )
    token = create_access_token(
        str(user.id),
        user.role,
        token_version=3,
    )

    current_user = await deps.get_current_user(
        credentials(token),
        ReadSession(user),
    )

    assert current_user is user


@pytest.mark.asyncio
async def test_incorrect_current_password_is_rejected(
    monkeypatch,
):
    install_fast_password_functions(
        monkeypatch
    )
    user = make_user()
    session = LockedSession(user)

    with pytest.raises(
        HTTPException
    ) as error:
        await auth.change_password(
            ChangePasswordRequest(
                current_password=(
                    "WrongPass123!"
                ),
                new_password=NEW_PASSWORD,
            ),
            user,
            session,
        )

    assert error.value.status_code == 400
    assert (
        error.value.detail
        == "Current password is incorrect."
    )
    assert session.commits == 0
    assert session.rollbacks == 0
    assert user.token_version == 0


@pytest.mark.asyncio
async def test_same_password_is_rejected(
    monkeypatch,
):
    install_fast_password_functions(
        monkeypatch
    )
    user = make_user()
    session = LockedSession(user)

    with pytest.raises(
        HTTPException
    ) as error:
        await auth.change_password(
            ChangePasswordRequest(
                current_password=OLD_PASSWORD,
                new_password=OLD_PASSWORD,
            ),
            user,
            session,
        )

    assert error.value.status_code == 400
    assert (
        error.value.detail
        == (
            "New password must be different "
            "from the current password."
        )
    )
    assert session.commits == 0
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_successful_change_invalidates_old_token_and_new_login_works(
    monkeypatch,
):
    install_fast_password_functions(
        monkeypatch
    )

    async def no_rate_limit(
        request,
        email,
    ):
        return None

    monkeypatch.setattr(
        auth,
        "enforce_login_rate_limit",
        no_rate_limit,
    )
    monkeypatch.setattr(
        auth,
        "clear_login_rate_limit",
        no_rate_limit,
    )

    user = make_user()
    old_token = create_access_token(
        str(user.id),
        user.role,
        user.token_version,
    )
    session = LockedSession(user)

    response = await auth.change_password(
        ChangePasswordRequest(
            current_password=OLD_PASSWORD,
            new_password=NEW_PASSWORD,
        ),
        SimpleNamespace(
            id=user.id,
            password_hash=user.password_hash,
            token_version=user.token_version,
        ),
        session,
    )

    assert (
        response.detail
        == (
            "Password updated. Sign in again "
            "with your new password."
        )
    )
    assert user.password_hash == (
        f"hash:{NEW_PASSWORD}"
    )
    assert user.token_version == 1
    assert session.commits == 1

    with pytest.raises(
        HTTPException
    ) as old_token_error:
        await deps.get_current_user(
            credentials(old_token),
            ReadSession(user),
        )

    assert (
        old_token_error.value.status_code
        == 401
    )

    login_response = await auth.login(
        SimpleNamespace(),
        LoginRequest(
            email=user.email,
            password=NEW_PASSWORD,
        ),
        ReadSession(user),
    )

    new_payload = decode_token(
        login_response.access_token
    )

    assert new_payload["ver"] == 1
    assert new_payload["sub"] == str(user.id)


@pytest.mark.asyncio
async def test_concurrent_password_changes_have_one_winner(
    monkeypatch,
):
    install_fast_password_functions(
        monkeypatch
    )

    user_id = uuid.uuid4()
    state = SharedCredentialState(
        user_id,
        f"hash:{OLD_PASSWORD}",
        0,
    )

    first_snapshot = SimpleNamespace(
        id=user_id,
        password_hash=(
            f"hash:{OLD_PASSWORD}"
        ),
        token_version=0,
    )
    second_snapshot = SimpleNamespace(
        id=user_id,
        password_hash=(
            f"hash:{OLD_PASSWORD}"
        ),
        token_version=0,
    )

    first_session = ConcurrentLockedSession(
        state
    )
    second_session = ConcurrentLockedSession(
        state
    )

    results = await asyncio.gather(
        auth.change_password(
            ChangePasswordRequest(
                current_password=OLD_PASSWORD,
                new_password=NEW_PASSWORD,
            ),
            first_snapshot,
            first_session,
        ),
        auth.change_password(
            ChangePasswordRequest(
                current_password=OLD_PASSWORD,
                new_password=(
                    SECOND_NEW_PASSWORD
                ),
            ),
            second_snapshot,
            second_session,
        ),
        return_exceptions=True,
    )

    successes = [
        result
        for result in results
        if not isinstance(
            result,
            Exception,
        )
    ]
    conflicts = [
        result
        for result in results
        if (
            isinstance(
                result,
                HTTPException,
            )
            and result.status_code == 409
        )
    ]

    assert len(successes) == 1
    assert len(conflicts) == 1
    assert state.user.token_version == 1
    assert state.user.password_hash in {
        f"hash:{NEW_PASSWORD}",
        f"hash:{SECOND_NEW_PASSWORD}",
    }
    assert (
        first_session.commits
        + second_session.commits
        == 1
    )
