from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.orders import (
    create_public_order,
)
from app.api.v1.store_publication import (
    AdminStorePublicationRequest,
    publish_store,
    unpublish_store,
)
from app.models import StorePublicationEvent
from app.schemas.order import PublicOrderCreate


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class FakeSession:
    def __init__(
        self,
        results=(),
        *,
        flush_error=None,
        commit_error=None,
    ):
        self.results = list(results)
        self.flush_error = flush_error
        self.commit_error = commit_error

        self.added = []
        self.commit_count = 0
        self.rollback_count = 0
        self.flush_count = 0

    async def execute(self, statement):
        del statement

        if not self.results:
            raise AssertionError(
                "Unexpected database query."
            )

        return FakeResult(
            self.results.pop(0)
        )

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_count += 1

        if self.flush_error is not None:
            raise self.flush_error

    async def commit(self):
        self.commit_count += 1

        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self):
        self.rollback_count += 1


def make_store(
    *,
    publication_status="draft",
):
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        id=uuid4(),
        owner_id=uuid4(),
        name="Launch Store",
        slug="launch-store",
        publication_status=(
            publication_status
        ),
        is_active=True,
        is_suspended=False,
        subscription_status="trial",
        trial_ends_at=(
            now + timedelta(days=14)
        ),
        subscription_ends_at=None,
        updated_at=now,
    )


def make_owner(
    *,
    role="merchant",
):
    return SimpleNamespace(
        id=uuid4(),
        role=role,
        password_hash=(
            "accepted-password-hash"
        ),
        is_verified=True,
        is_active=True,
    )


def make_admin(
    *,
    role="platform_admin",
):
    return SimpleNamespace(
        id=uuid4(),
        role=role,
    )


@pytest.mark.asyncio
async def test_admin_can_publish_valid_trial_store():
    store = make_store()
    admin = make_admin()

    session = FakeSession(
        [
            store,
            make_owner(),
            1,
        ]
    )

    operational_snapshot = (
        store.is_active,
        store.is_suspended,
        store.subscription_status,
        store.trial_ends_at,
    )

    response = await publish_store(
        store_id=store.id,
        payload=(
            AdminStorePublicationRequest(
                expected_updated_at=(
                    store.updated_at
                ),
                reason=(
                    "  Launch approval  "
                ),
            )
        ),
        current_admin=admin,
        db=session,
    )

    assert response is store
    assert (
        store.publication_status
        == "published"
    )

    assert (
        store.is_active,
        store.is_suspended,
        store.subscription_status,
        store.trial_ends_at,
    ) == operational_snapshot

    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert session.flush_count == 1
    assert len(session.added) == 1

    event = session.added[0]

    assert isinstance(
        event,
        StorePublicationEvent,
    )

    assert event.store_id == store.id
    assert event.actor_user_id == admin.id
    assert event.actor_role == admin.role
    assert event.action == "publish"

    assert (
        event.previous_publication_status
        == "draft"
    )

    assert (
        event.new_publication_status
        == "published"
    )

    assert event.reason == "Launch approval"

    assert (
        event.readiness_snapshot[
            "active_product_count"
        ]
        == 1
    )

    assert (
        event.readiness_snapshot[
            "publish_ready"
        ]
        is True
    )

    assert (
        event.readiness_snapshot[
            "blockers"
        ]
        == []
    )


@pytest.mark.asyncio
async def test_publish_requires_active_product():
    store = make_store()

    session = FakeSession(
        [
            store,
            make_owner(),
            0,
        ]
    )

    with pytest.raises(
        HTTPException
    ) as captured:
        await publish_store(
            store_id=store.id,
            payload=(
                AdminStorePublicationRequest(
                    expected_updated_at=(
                        store.updated_at
                    )
                )
            ),
            current_admin=make_admin(),
            db=session,
        )

    assert captured.value.status_code == 409

    assert (
        "At least one active product"
        in str(captured.value.detail)
    )

    assert (
        store.publication_status
        == "draft"
    )

    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.flush_count == 0
    assert session.added == []


@pytest.mark.asyncio
async def test_unpublish_preserves_store_state():
    store = make_store(
        publication_status="published",
    )

    admin = make_admin()

    session = FakeSession(
        [
            store,
            make_owner(),
            1,
        ]
    )

    operational_snapshot = (
        store.is_active,
        store.is_suspended,
        store.subscription_status,
        store.trial_ends_at,
    )

    await unpublish_store(
        store_id=store.id,
        payload=(
            AdminStorePublicationRequest(
                expected_updated_at=(
                    store.updated_at
                ),
                reason=(
                    "Temporary maintenance"
                ),
            )
        ),
        current_admin=admin,
        db=session,
    )

    assert (
        store.publication_status
        == "draft"
    )

    assert (
        store.is_active,
        store.is_suspended,
        store.subscription_status,
        store.trial_ends_at,
    ) == operational_snapshot

    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert session.flush_count == 1
    assert len(session.added) == 1

    event = session.added[0]

    assert isinstance(
        event,
        StorePublicationEvent,
    )

    assert event.action == "unpublish"

    assert (
        event.previous_publication_status
        == "published"
    )

    assert (
        event.new_publication_status
        == "draft"
    )

    assert (
        event.reason
        == "Temporary maintenance"
    )


@pytest.mark.asyncio
async def test_stale_publication_request_is_rejected():
    store = make_store()

    stale_timestamp = (
        store.updated_at
        - timedelta(seconds=1)
    )

    session = FakeSession([store])

    with pytest.raises(
        HTTPException
    ) as captured:
        await publish_store(
            store_id=store.id,
            payload=(
                AdminStorePublicationRequest(
                    expected_updated_at=(
                        stale_timestamp
                    )
                )
            ),
            current_admin=make_admin(),
            db=session,
        )

    assert captured.value.status_code == 409
    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.flush_count == 0
    assert session.added == []


@pytest.mark.asyncio
async def test_non_admin_cannot_call_transition_directly():
    store = make_store()
    session = FakeSession()

    with pytest.raises(
        HTTPException
    ) as captured:
        await publish_store(
            store_id=store.id,
            payload=(
                AdminStorePublicationRequest(
                    expected_updated_at=(
                        store.updated_at
                    )
                )
            ),
            current_admin=make_owner(),
            db=session,
        )

    assert captured.value.status_code == 403
    assert session.commit_count == 0
    assert session.rollback_count == 0
    assert session.flush_count == 0
    assert session.added == []


@pytest.mark.asyncio
async def test_same_state_does_not_create_event():
    store = make_store(
        publication_status="published",
    )

    original_updated_at = store.updated_at

    session = FakeSession([store])

    response = await publish_store(
        store_id=store.id,
        payload=(
            AdminStorePublicationRequest(
                expected_updated_at=(
                    store.updated_at
                )
            )
        ),
        current_admin=make_admin(),
        db=session,
    )

    assert response is store

    assert (
        store.publication_status
        == "published"
    )

    assert store.updated_at == original_updated_at
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert session.flush_count == 0
    assert session.added == []


@pytest.mark.asyncio
async def test_event_flush_failure_rolls_back_transition():
    store = make_store()

    session = FakeSession(
        [
            store,
            make_owner(),
            1,
        ],
        flush_error=RuntimeError(
            "simulated event flush failure"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="simulated event flush failure",
    ):
        await publish_store(
            store_id=store.id,
            payload=(
                AdminStorePublicationRequest(
                    expected_updated_at=(
                        store.updated_at
                    )
                )
            ),
            current_admin=make_admin(),
            db=session,
        )

    assert session.flush_count == 1
    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_draft_store_order_is_concealed():
    store = make_store()

    session = FakeSession(
        [
            store,
            None,
            None,
        ]
    )

    payload = PublicOrderCreate(
        store_slug=store.slug,
        customer_name="Draft Customer",
        customer_phone="0241234567",
        items=[
            {
                "product_id": uuid4(),
                "quantity": 1,
            }
        ],
    )

    with pytest.raises(
        HTTPException
    ) as captured:
        await create_public_order(
            payload=payload,
            idempotency_key=(
                "draft-order-test-"
                "0123456789abcdef"
            ),
            db=session,
        )

    assert captured.value.status_code == 404

    assert (
        captured.value.detail
        == "Store not found"
    )

    assert session.commit_count == 0
