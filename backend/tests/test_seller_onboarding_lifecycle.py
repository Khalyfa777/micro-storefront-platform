from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request

import app.api.v1.invitations as invitation_api
import app.api.v1.sellers as sellers_api
from app.api.v1.seller_accounts import (
    reactivate_seller_account,
    suspend_seller_account,
)
from app.models import (
    SellerAccountEvent,
    SellerInvitation,
)
from app.schemas.seller import (
    AdminSellerAccountActionRequest,
    AdminSellerInvitationRegenerateRequest,
    AdminSellerOnboardingCancelRequest,
    SellerInvitationAcceptRequest,
    SellerInvitationTokenRequest,
)
from app.services.seller_invitation import (
    hash_invitation_token,
)


TEST_TOKEN = (
    "storeplug-controlled-invitation-token-"
    "0123456789"
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, results=()):
        self.results = list(results)
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0
        self.flush_count = 0

    async def execute(self, statement):
        del statement

        if not self.results:
            raise AssertionError(
                "Unexpected database execute call."
            )

        return FakeResult(
            self.results.pop(0)
        )

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_count += 1

        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid4()

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


def make_request(
    path: str = (
        "/api/v1/"
        "seller-invitations/validate"
    ),
) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "client": (
                "203.0.113.20",
                51000,
            ),
            "server": (
                "api.storeplughq.com",
                443,
            ),
        }
    )


def make_pending_seller():
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=uuid4(),
        email="pending@example.com",
        full_name="Pending Seller",
        role="merchant",
        password_hash=None,
        is_active=False,
        is_verified=False,
        created_at=now,
        updated_at=now,
    )


def make_store(seller_id):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=uuid4(),
        owner_id=seller_id,
        name="Controlled Store",
        slug="controlled-store",
        publication_status="draft",
        is_active=True,
        is_suspended=False,
        plan_name="starter",
        subscription_status="trial",
        trial_ends_at=(
            now + timedelta(days=14)
        ),
        subscription_ends_at=None,
        monthly_fee="0.00",
        created_at=now,
    )


def make_invitation(
    seller_id,
    store_id,
    *,
    accepted_at=None,
    revoked_at=None,
    expires_at=None,
):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=uuid4(),
        user_id=seller_id,
        store_id=store_id,
        token_hash=hash_invitation_token(
            TEST_TOKEN
        ),
        accepted_at=accepted_at,
        revoked_at=revoked_at,
        expires_at=(
            expires_at
            or now + timedelta(hours=24)
        ),
        created_at=now,
        updated_at=now,
    )


def snapshot_store(store):
    return (
        store.id,
        store.owner_id,
        store.publication_status,
        store.is_active,
        store.is_suspended,
        store.plan_name,
        store.subscription_status,
        store.trial_ends_at,
        store.subscription_ends_at,
        store.monthly_fee,
    )


async def allow_invitation_attempt(
    request,
    action,
):
    del request
    del action


@pytest.mark.asyncio
async def test_active_invitation_validates(
    monkeypatch,
):
    monkeypatch.setattr(
        invitation_api,
        "enforce_seller_invitation_rate_limit",
        allow_invitation_attempt,
    )

    seller = make_pending_seller()
    store = make_store(seller.id)
    invitation = make_invitation(
        seller.id,
        store.id,
    )

    session = FakeSession(
        [
            invitation,
            seller,
            store,
        ]
    )

    result = await invitation_api\
        .validate_seller_invitation(
            make_request(),
            SellerInvitationTokenRequest(
                token=TEST_TOKEN
            ),
            session,
        )

    assert result.valid is True
    assert result.seller_id == seller.id
    assert result.store_id == store.id
    assert result.publication_status == "draft"
    assert session.commit_count == 0
    assert session.rollback_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "accepted_at",
        "revoked_at",
        "expires_at",
        "status_code",
        "detail",
    ),
    [
        (
            datetime.now(timezone.utc),
            None,
            datetime.now(timezone.utc)
            + timedelta(hours=1),
            409,
            (
                "This invitation has already "
                "been used."
            ),
        ),
        (
            None,
            datetime.now(timezone.utc),
            datetime.now(timezone.utc)
            + timedelta(hours=1),
            410,
            (
                "This invitation is no longer "
                "valid."
            ),
        ),
        (
            None,
            None,
            datetime.now(timezone.utc)
            - timedelta(minutes=1),
            410,
            "This invitation has expired.",
        ),
    ],
)
async def test_unusable_invitation_validation(
    monkeypatch,
    accepted_at,
    revoked_at,
    expires_at,
    status_code,
    detail,
):
    monkeypatch.setattr(
        invitation_api,
        "enforce_seller_invitation_rate_limit",
        allow_invitation_attempt,
    )

    seller = make_pending_seller()
    store = make_store(seller.id)

    invitation = make_invitation(
        seller.id,
        store.id,
        accepted_at=accepted_at,
        revoked_at=revoked_at,
        expires_at=expires_at,
    )

    session = FakeSession([invitation])

    with pytest.raises(
        HTTPException
    ) as error:
        await invitation_api\
            .validate_seller_invitation(
                make_request(),
                SellerInvitationTokenRequest(
                    token=TEST_TOKEN
                ),
                session,
            )

    assert error.value.status_code == status_code
    assert error.value.detail == detail


@pytest.mark.asyncio
async def test_unknown_invitation_returns_404(
    monkeypatch,
):
    monkeypatch.setattr(
        invitation_api,
        "enforce_seller_invitation_rate_limit",
        allow_invitation_attempt,
    )

    session = FakeSession([None])

    with pytest.raises(
        HTTPException
    ) as error:
        await invitation_api\
            .validate_seller_invitation(
                make_request(),
                SellerInvitationTokenRequest(
                    token=TEST_TOKEN
                ),
                session,
            )

    assert error.value.status_code == 404
    assert (
        error.value.detail
        == "Invitation not found."
    )


@pytest.mark.asyncio
async def test_acceptance_activates_account_but_keeps_store_draft(
    monkeypatch,
):
    monkeypatch.setattr(
        invitation_api,
        "enforce_seller_invitation_rate_limit",
        allow_invitation_attempt,
    )

    async def controlled_threadpool(
        function,
        password,
    ):
        del function
        del password
        return "controlled-password-hash"

    monkeypatch.setattr(
        invitation_api,
        "run_in_threadpool",
        controlled_threadpool,
    )

    seller = make_pending_seller()
    store = make_store(seller.id)
    invitation = make_invitation(
        seller.id,
        store.id,
    )

    before_store = snapshot_store(store)

    candidate = (
        invitation.id,
        seller.id,
    )

    session = FakeSession(
        [
            candidate,
            seller,
            invitation,
            store,
        ]
    )

    payload = SellerInvitationAcceptRequest(
        token=TEST_TOKEN,
        password="StrongPass123!",
    )

    result = await invitation_api\
        .accept_seller_invitation(
            make_request(
                "/api/v1/"
                "seller-invitations/accept"
            ),
            payload,
            session,
        )

    assert result.account_status == "active"
    assert result.publication_status == "draft"

    assert seller.password_hash == (
        "controlled-password-hash"
    )
    assert seller.is_active is True
    assert seller.is_verified is True
    assert invitation.accepted_at is not None

    assert snapshot_store(store) == before_store
    assert session.commit_count == 1
    assert session.rollback_count == 0

    reused_session = FakeSession(
        [
            candidate,
            seller,
            invitation,
        ]
    )

    with pytest.raises(
        HTTPException
    ) as reused_error:
        await invitation_api\
            .accept_seller_invitation(
                make_request(
                    "/api/v1/"
                    "seller-invitations/accept"
                ),
                payload,
                reused_session,
            )

    assert reused_error.value.status_code == 409
    assert reused_error.value.detail == (
        "This invitation has already been used."
    )
    assert reused_session.rollback_count == 1


@pytest.mark.asyncio
async def test_regeneration_revokes_previous_invitation(
    monkeypatch,
):
    seller = make_pending_seller()
    store = make_store(seller.id)
    invitation = make_invitation(
        seller.id,
        store.id,
    )

    replacement_token = (
        "replacement-controlled-token-"
        "01234567890123456789"
    )

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(hours=72)
    )

    monkeypatch.setattr(
        sellers_api,
        "generate_invitation_token",
        lambda: replacement_token,
    )

    monkeypatch.setattr(
        sellers_api,
        "get_invitation_expiry",
        lambda now: expires_at,
    )

    admin = SimpleNamespace(id=uuid4())

    session = FakeSession(
        [
            seller,
            invitation,
            store,
        ]
    )

    before_store = snapshot_store(store)

    result = await sellers_api\
        .regenerate_seller_invitation(
            seller.id,
            AdminSellerInvitationRegenerateRequest(
                current_invitation_id=(
                    invitation.id
                )
            ),
            admin,
            session,
        )

    assert invitation.revoked_at is not None
    assert snapshot_store(store) == before_store

    replacements = [
        item
        for item in session.added
        if isinstance(
            item,
            SellerInvitation,
        )
    ]

    assert len(replacements) == 1

    replacement = replacements[0]

    assert replacement.id == result.invitation_id
    assert replacement.user_id == seller.id
    assert replacement.store_id == store.id
    assert replacement.accepted_at is None
    assert replacement.revoked_at is None
    assert replacement.expires_at == expires_at

    assert replacement.token_hash == (
        hash_invitation_token(
            replacement_token
        )
    )

    assert (
        replacement.token_hash
        != replacement_token
    )

    assert "#token=" in result.invitation_url
    assert session.flush_count == 2
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_stale_regeneration_is_rejected():
    seller = make_pending_seller()
    store = make_store(seller.id)
    invitation = make_invitation(
        seller.id,
        store.id,
    )

    session = FakeSession(
        [
            seller,
            invitation,
        ]
    )

    admin = SimpleNamespace(id=uuid4())

    with pytest.raises(
        HTTPException
    ) as error:
        await sellers_api\
            .regenerate_seller_invitation(
                seller.id,
                AdminSellerInvitationRegenerateRequest(
                    current_invitation_id=uuid4()
                ),
                admin,
                session,
            )

    assert error.value.status_code == 409
    assert error.value.detail == (
        "The invitation has already changed. "
        "Refresh and try again."
    )

    assert invitation.revoked_at is None
    assert session.added == []
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_cancellation_revokes_invitation_and_retains_entities():
    seller = make_pending_seller()
    store = make_store(seller.id)
    invitation = make_invitation(
        seller.id,
        store.id,
    )

    before_seller = (
        seller.id,
        seller.password_hash,
        seller.is_active,
        seller.is_verified,
    )

    before_store = snapshot_store(store)

    session = FakeSession(
        [
            seller,
            invitation,
        ]
    )

    result = await sellers_api\
        .cancel_seller_onboarding(
            seller.id,
            AdminSellerOnboardingCancelRequest(
                current_invitation_id=(
                    invitation.id
                )
            ),
            SimpleNamespace(id=uuid4()),
            session,
        )

    assert result.onboarding_status == "cancelled"
    assert invitation.revoked_at is not None

    assert (
        seller.id,
        seller.password_hash,
        seller.is_active,
        seller.is_verified,
    ) == before_seller

    assert snapshot_store(store) == before_store
    assert session.commit_count == 1
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_account_actions_preserve_store_and_reject_stale_write():
    initial_updated_at = (
        datetime.now(timezone.utc)
        - timedelta(hours=1)
    )

    seller = SimpleNamespace(
        id=uuid4(),
        role="merchant",
        password_hash="stored-password-hash",
        is_active=True,
        is_verified=True,
        updated_at=initial_updated_at,
    )

    store = make_store(seller.id)
    store.publication_status = "published"
    store.plan_name = "business"
    store.subscription_status = "active"
    store.monthly_fee = "80.00"

    before_store = snapshot_store(store)
    admin = SimpleNamespace(id=uuid4())

    suspend_session = FakeSession([seller])

    suspended = await suspend_seller_account(
        seller.id,
        AdminSellerAccountActionRequest(
            expected_updated_at=(
                initial_updated_at
            ),
            reason="Controlled suspension",
        ),
        admin,
        suspend_session,
    )

    assert suspended.account_status == "suspended"
    assert seller.is_active is False
    assert seller.is_verified is True
    assert seller.password_hash == (
        "stored-password-hash"
    )
    assert snapshot_store(store) == before_store

    suspend_events = [
        item
        for item in suspend_session.added
        if isinstance(
            item,
            SellerAccountEvent,
        )
    ]

    assert len(suspend_events) == 1
    assert suspend_events[0].action == "suspend"

    stale_session = FakeSession([seller])

    with pytest.raises(
        HTTPException
    ) as stale_error:
        await suspend_seller_account(
            seller.id,
            AdminSellerAccountActionRequest(
                expected_updated_at=(
                    initial_updated_at
                ),
                reason="Stale duplicate",
            ),
            admin,
            stale_session,
        )

    assert stale_error.value.status_code == 409
    assert stale_error.value.detail == (
        "Seller account changed. "
        "Refresh and try again."
    )
    assert stale_session.added == []
    assert stale_session.rollback_count == 1

    reactivate_session = FakeSession([seller])

    reactivated = await reactivate_seller_account(
        seller.id,
        AdminSellerAccountActionRequest(
            expected_updated_at=(
                suspended.updated_at
            ),
            reason="Controlled reactivation",
        ),
        admin,
        reactivate_session,
    )

    assert reactivated.account_status == "active"
    assert seller.is_active is True
    assert seller.is_verified is True
    assert seller.password_hash == (
        "stored-password-hash"
    )
    assert snapshot_store(store) == before_store

    reactivate_events = [
        item
        for item in reactivate_session.added
        if isinstance(
            item,
            SellerAccountEvent,
        )
    ]

    assert len(reactivate_events) == 1
    assert (
        reactivate_events[0].action
        == "reactivate"
    )

    assert (
        len(suspend_events)
        + len(stale_session.added)
        + len(reactivate_events)
        == 2
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "action",
        "expected_detail",
    ),
    [
        (
            suspend_seller_account,
            (
                "Invited sellers must use "
                "onboarding cancellation instead."
            ),
        ),
        (
            reactivate_seller_account,
            (
                "Seller onboarding has not "
                "been completed."
            ),
        ),
    ],
)
async def test_invited_account_actions_are_rejected(
    action,
    expected_detail,
):
    seller = make_pending_seller()
    session = FakeSession([seller])

    with pytest.raises(
        HTTPException
    ) as error:
        await action(
            seller.id,
            AdminSellerAccountActionRequest(
                expected_updated_at=(
                    seller.updated_at
                ),
                reason="Invalid account action",
            ),
            SimpleNamespace(id=uuid4()),
            session,
        )

    assert error.value.status_code == 409
    assert error.value.detail == expected_detail
    assert session.added == []
    assert session.rollback_count == 1