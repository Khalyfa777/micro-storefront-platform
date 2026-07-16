from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.stores import (
    AdminExtendSubscriptionPayload,
    AdminStoreStatusUpdate,
    admin_extend_store_subscription,
    admin_update_store_status,
)
from app.models import StoreAccessEvent
from app.services.subscription import (
    build_subscription_request_fingerprint,
    get_store_access_error,
)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(
        self,
        results=(),
        *,
        flush_error=None,
    ):
        self.results = list(results)
        self.flush_error = flush_error
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0
        self.refresh_count = 0
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

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1

    async def flush(self):
        self.flush_count += 1

        if self.flush_error is not None:
            raise self.flush_error

    async def refresh(self, value):
        del value
        self.refresh_count += 1


def make_store(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid4(),
        "plan_name": "starter",
        "monthly_fee": Decimal("0.00"),
        "last_payment_at": None,
        "subscription_status": "trial",
        "trial_ends_at": now + timedelta(days=14),
        "subscription_ends_at": None,
        "is_suspended": False,
        "is_active": True,
        "updated_at": now,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_plan():
    return SimpleNamespace(
        name="starter",
        monthly_fee=Decimal("30.00"),
        is_active=True,
    )


def make_admin():
    return SimpleNamespace(
        id=uuid4(),
        role="platform_admin",
    )


def make_payload():
    return AdminExtendSubscriptionPayload(
        plan_name="starter",
        amount_paid=Decimal("30.00"),
        extend_days=30,
        payment_method="momo",
        payment_reference="MOMO-123",
        note="Starter renewal",
        mark_active=True,
    )


@pytest.mark.asyncio
async def test_subscription_payment_replay_has_single_effect():
    store = make_store()
    admin = make_admin()
    payload = make_payload()
    key = "subscription-11111111-2222"

    first_session = FakeSession(
        [store, None, None, make_plan()]
    )

    await admin_extend_store_subscription(
        store_id=store.id,
        payload=payload,
        idempotency_key=key,
        current_user=admin,
        db=first_session,
    )

    assert len(first_session.added) == 1
    payment = first_session.added[0]
    first_end = store.subscription_ends_at

    assert payment.idempotency_key == key
    assert len(payment.request_fingerprint) == 64
    assert first_session.commit_count == 1

    replay_session = FakeSession(
        [store, payment]
    )

    await admin_extend_store_subscription(
        store_id=store.id,
        payload=payload,
        idempotency_key=key,
        current_user=admin,
        db=replay_session,
    )

    assert replay_session.added == []
    assert replay_session.commit_count == 1
    assert store.subscription_ends_at == first_end


@pytest.mark.asyncio
async def test_idempotency_key_reuse_with_different_request_is_rejected():
    store = make_store()
    admin = make_admin()
    payload = make_payload()
    key = "subscription-33333333-4444"
    fingerprint = build_subscription_request_fingerprint(
        store_id=store.id,
        approved_by_user_id=admin.id,
        plan_name=payload.plan_name,
        amount_paid=Decimal("80.00"),
        extend_days=payload.extend_days,
        payment_method=payload.payment_method,
        payment_reference=payload.payment_reference,
        note=payload.note,
        mark_active=payload.mark_active,
    )
    existing_payment = SimpleNamespace(
        request_fingerprint=fingerprint,
    )
    session = FakeSession(
        [store, existing_payment]
    )

    with pytest.raises(
        HTTPException
    ) as captured:
        await admin_extend_store_subscription(
            store_id=store.id,
            payload=payload,
            idempotency_key=key,
            current_user=admin,
            db=session,
        )

    assert captured.value.status_code == 409
    assert session.added == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_external_payment_reference_cannot_be_recorded_twice():
    store = make_store()
    admin = make_admin()
    payload = make_payload()
    existing_reference = SimpleNamespace(
        id=uuid4(),
    )
    session = FakeSession(
        [store, None, existing_reference]
    )

    with pytest.raises(
        HTTPException
    ) as captured:
        await admin_extend_store_subscription(
            store_id=store.id,
            payload=payload,
            idempotency_key=(
                "subscription-55555555-6666"
            ),
            current_user=admin,
            db=session,
        )

    assert captured.value.status_code == 409
    assert session.added == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_unsuspending_expired_legacy_store_does_not_activate_subscription():
    now = datetime.now(timezone.utc)
    store = make_store(
        subscription_status="suspended",
        trial_ends_at=now - timedelta(days=2),
        subscription_ends_at=None,
        is_suspended=True,
        is_active=False,
    )
    session = FakeSession([store])

    await admin_update_store_status(
        store_id=store.id,
        payload=AdminStoreStatusUpdate(
            is_suspended=False,
            is_active=True,
        ),
        current_user=make_admin(),
        db=session,
    )

    assert store.is_suspended is False
    assert store.is_active is True
    assert store.subscription_status == "expired"
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_unsuspending_valid_paid_store_restores_active_status():
    now = datetime.now(timezone.utc)
    store = make_store(
        subscription_status="suspended",
        trial_ends_at=now - timedelta(days=2),
        subscription_ends_at=(
            now + timedelta(days=10)
        ),
        is_suspended=True,
    )
    session = FakeSession([store])

    await admin_update_store_status(
        store_id=store.id,
        payload=AdminStoreStatusUpdate(
            is_suspended=False,
        ),
        current_user=make_admin(),
        db=session,
    )

    assert store.is_suspended is False
    assert store.subscription_status == "active"


@pytest.mark.asyncio
async def test_suspension_does_not_overwrite_valid_subscription_state():
    store = make_store(
        subscription_status="active",
        subscription_ends_at=(
            datetime.now(timezone.utc)
            + timedelta(days=10)
        ),
    )
    session = FakeSession([store])

    await admin_update_store_status(
        store_id=store.id,
        payload=AdminStoreStatusUpdate(
            is_suspended=True,
        ),
        current_user=make_admin(),
        db=session,
    )

    assert store.is_suspended is True
    assert store.subscription_status == "active"


def test_active_subscription_without_expiry_is_blocked():
    store = make_store(
        subscription_status="active",
        subscription_ends_at=None,
    )

    assert get_store_access_error(store) == (
        "This store is temporarily unavailable."
    )


def test_status_payload_rejects_direct_subscription_activation():
    with pytest.raises(ValidationError):
        AdminStoreStatusUpdate(
            subscription_status="active",
            is_suspended=False,
        )

@pytest.mark.asyncio
async def test_subscription_payment_preserves_operational_access_state():
    now = datetime.now(timezone.utc)
    store = make_store(
        subscription_status="expired",
        trial_ends_at=(
            now - timedelta(days=2)
        ),
        subscription_ends_at=None,
        is_suspended=True,
        is_active=False,
    )
    session = FakeSession(
        [store, None, None, make_plan()]
    )

    await admin_extend_store_subscription(
        store_id=store.id,
        payload=make_payload(),
        idempotency_key=(
            "subscription-preserve-access-001"
        ),
        current_user=make_admin(),
        db=session,
    )

    assert store.subscription_status == "active"
    assert store.is_suspended is True
    assert store.is_active is False
    assert len(session.added) == 1
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_store_access_transition_creates_audit_event():
    store = make_store(
        subscription_status="active",
    )
    admin = make_admin()
    session = FakeSession([store])

    await admin_update_store_status(
        store_id=store.id,
        payload=AdminStoreStatusUpdate(
            is_active=False,
            is_suspended=True,
            note="  Fraud review  ",
        ),
        current_user=admin,
        db=session,
    )

    assert store.is_active is False
    assert store.is_suspended is True
    assert store.subscription_status == "active"
    assert session.flush_count == 1
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert len(session.added) == 1

    event = session.added[0]

    assert isinstance(
        event,
        StoreAccessEvent,
    )
    assert event.store_id == store.id
    assert event.actor_user_id == admin.id
    assert event.actor_role == admin.role
    assert event.action == "suspend"
    assert event.previous_is_active is True
    assert event.new_is_active is False
    assert event.previous_is_suspended is False
    assert event.new_is_suspended is True
    assert (
        event.previous_subscription_status
        == "active"
    )
    assert (
        event.new_subscription_status
        == "active"
    )
    assert event.reason == "Fraud review"


@pytest.mark.asyncio
async def test_store_access_noop_is_rejected_without_event():
    store = make_store()
    session = FakeSession([store])

    with pytest.raises(
        HTTPException
    ) as captured:
        await admin_update_store_status(
            store_id=store.id,
            payload=AdminStoreStatusUpdate(
                is_active=True,
                is_suspended=False,
            ),
            current_user=make_admin(),
            db=session,
        )

    assert captured.value.status_code == 409
    assert session.added == []
    assert session.flush_count == 0
    assert session.commit_count == 0
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_store_access_event_failure_rolls_back_transition():
    store = make_store()
    session = FakeSession(
        [store],
        flush_error=RuntimeError(
            "simulated store access event failure"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "simulated store access event failure"
        ),
    ):
        await admin_update_store_status(
            store_id=store.id,
            payload=AdminStoreStatusUpdate(
                is_suspended=True,
            ),
            current_user=make_admin(),
            db=session,
        )

    assert session.flush_count == 1
    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert len(session.added) == 1
