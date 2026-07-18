import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.v1.seller_accounts import (
    reactivate_seller_account,
    suspend_seller_account,
)
from app.models import (
    SellerAccountEvent,
    Store,
    User,
)
from app.schemas.seller import (
    AdminSellerAccountActionRequest,
)


EXPECTED_ALEMBIC_HEAD = "f0a2b4d6e8c1"


class StartGate:
    def __init__(self, participants: int) -> None:
        self.participants = participants
        self.arrived = 0
        self.lock = asyncio.Lock()
        self.ready = asyncio.Event()

    async def wait(self) -> None:
        async with self.lock:
            self.arrived += 1

            if self.arrived == self.participants:
                self.ready.set()

        await self.ready.wait()


def validated_test_database_url() -> URL:
    raw_url = os.environ.get(
        "TEST_DATABASE_URL",
        "",
    ).strip()

    if not raw_url:
        pytest.skip(
            "TEST_DATABASE_URL is not configured."
        )

    url = make_url(raw_url)
    database_name = url.database or ""

    if "test" not in database_name.lower():
        pytest.fail(
            "Safety stop: TEST_DATABASE_URL must "
            "target a database containing 'test'."
        )

    if url.drivername != "postgresql+asyncpg":
        pytest.fail(
            "Integration tests require "
            "postgresql+asyncpg."
        )

    return url


@pytest_asyncio.fixture
async def test_database():
    url = validated_test_database_url()

    engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
    )

    sessions = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    try:
        async with engine.connect() as connection:
            current_database = await connection.scalar(
                text("SELECT current_database()")
            )

            current_revision = await connection.scalar(
                text(
                    """
                    SELECT version_num
                    FROM alembic_version
                    """
                )
            )

        assert current_database == url.database
        assert current_revision == EXPECTED_ALEMBIC_HEAD

        yield engine, sessions

    finally:
        await engine.dispose()


async def create_fixture(
    sessions: async_sessionmaker[AsyncSession],
    *,
    label: str,
    is_active: bool,
) -> dict:
    suffix = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    initial_updated_at = now - timedelta(hours=1)

    async with sessions() as session:
        admin = User(
            email=(
                f"phase4b6d2-admin-{label}-"
                f"{suffix}@example.com"
            ),
            full_name="Phase 4B6D2 Admin",
            password_hash="integration-admin-hash",
            role="platform_admin",
            is_active=True,
            is_verified=True,
        )

        seller = User(
            email=(
                f"phase4b6d2-{label}-"
                f"{suffix}@example.com"
            ),
            full_name=(
                f"Phase 4B6D2 {label} Seller"
            ),
            password_hash=(
                "integration-seller-password-hash"
            ),
            role="merchant",
            is_active=is_active,
            is_verified=True,
            created_at=initial_updated_at,
            updated_at=initial_updated_at,
        )

        session.add_all([admin, seller])
        await session.flush()

        store = Store(
            owner_id=seller.id,
            slug=(
                f"phase4b6d2-{label}-{suffix}"
            ),
            name=(
                f"Phase 4B6D2 {label} Store"
            ),
            social_links={},
            theme="default",
            is_active=True,
            is_suspended=False,
            publication_status="published",
            plan_name="business",
            subscription_status="active",
            trial_ends_at=now,
            subscription_ends_at=(
                now + timedelta(days=30)
            ),
            monthly_fee=Decimal("80.00"),
        )

        session.add(store)
        await session.commit()

        return {
            "admin_id": admin.id,
            "seller_id": seller.id,
            "store_id": store.id,
            "updated_at": initial_updated_at,
            "password_hash": seller.password_hash,
        }


async def cleanup_fixture(
    sessions: async_sessionmaker[AsyncSession],
    fixture: dict,
) -> None:
    async with sessions() as session:
        await session.execute(
            delete(SellerAccountEvent).where(
                SellerAccountEvent.seller_id
                == fixture["seller_id"]
            )
        )

        await session.execute(
            delete(Store).where(
                Store.owner_id
                == fixture["seller_id"]
            )
        )

        await session.execute(
            delete(User).where(
                User.id.in_(
                    [
                        fixture["seller_id"],
                        fixture["admin_id"],
                    ]
                )
            )
        )

        await session.commit()


async def store_snapshot(
    sessions: async_sessionmaker[AsyncSession],
    seller_id,
) -> list[tuple]:
    async with sessions() as session:
        stores = list(
            (
                await session.scalars(
                    select(Store)
                    .where(
                        Store.owner_id == seller_id
                    )
                    .order_by(Store.id)
                )
            ).all()
        )

        return [
            (
                store.id,
                store.publication_status,
                store.is_active,
                store.is_suspended,
                store.plan_name,
                store.subscription_status,
                store.trial_ends_at,
                store.subscription_ends_at,
                store.monthly_fee,
            )
            for store in stores
        ]


async def run_action(
    sessions: async_sessionmaker[AsyncSession],
    *,
    action_name: str,
    seller_id,
    admin_id,
    expected_updated_at,
    reason: str,
    gate: StartGate,
) -> dict:
    async with sessions() as session:
        admin = await session.scalar(
            select(User).where(
                User.id == admin_id
            )
        )

        assert admin is not None

        await gate.wait()

        payload = AdminSellerAccountActionRequest(
            expected_updated_at=(
                expected_updated_at
            ),
            reason=reason,
        )

        try:
            if action_name == "suspend":
                response = (
                    await suspend_seller_account(
                        seller_id,
                        payload,
                        admin,
                        session,
                    )
                )

            elif action_name == "reactivate":
                response = (
                    await reactivate_seller_account(
                        seller_id,
                        payload,
                        admin,
                        session,
                    )
                )

            else:
                raise AssertionError(
                    f"Unknown action: {action_name}"
                )

            return {
                "kind": "success",
                "action": action_name,
                "response": response,
            }

        except HTTPException as exc:
            return {
                "kind": "http",
                "action": action_name,
                "status_code": exc.status_code,
                "detail": exc.detail,
            }


async def execute_race(
    sessions: async_sessionmaker[AsyncSession],
    first: dict,
    second: dict,
) -> list[dict]:
    gate = StartGate(2)

    return await asyncio.wait_for(
        asyncio.gather(
            run_action(
                sessions,
                **first,
                gate=gate,
            ),
            run_action(
                sessions,
                **second,
                gate=gate,
            ),
        ),
        timeout=20,
    )


def assert_one_winner(
    results: list[dict],
    *,
    expected_action: str,
    allowed_conflicts: set[str],
) -> None:
    successes = [
        result
        for result in results
        if result["kind"] == "success"
    ]

    conflicts = [
        result
        for result in results
        if result["kind"] == "http"
    ]

    assert len(successes) == 1, results
    assert len(conflicts) == 1, results

    assert (
        successes[0]["action"]
        == expected_action
    )

    assert conflicts[0]["status_code"] == 409
    assert (
        conflicts[0]["detail"]
        in allowed_conflicts
    )


async def verify_final_state(
    sessions: async_sessionmaker[AsyncSession],
    *,
    fixture: dict,
    expected_active: bool,
    expected_action: str,
    before_stores: list[tuple],
) -> None:
    async with sessions() as session:
        seller = await session.scalar(
            select(User).where(
                User.id == fixture["seller_id"]
            )
        )

        assert seller is not None
        assert seller.is_active is expected_active
        assert seller.is_verified is True
        assert (
            seller.password_hash
            == fixture["password_hash"]
        )

        events = list(
            (
                await session.scalars(
                    select(SellerAccountEvent)
                    .where(
                        SellerAccountEvent.seller_id
                        == fixture["seller_id"]
                    )
                    .order_by(
                        SellerAccountEvent
                        .created_at.desc(),
                        SellerAccountEvent.id.desc(),
                    )
                )
            ).all()
        )

        assert len(events) == 1
        assert events[0].action == expected_action
        assert (
            events[0].actor_user_id
            == fixture["admin_id"]
        )

        if expected_action == "suspend":
            assert (
                events[0]
                .previous_account_status
                == "active"
            )
            assert (
                events[0].new_account_status
                == "suspended"
            )

        else:
            assert (
                events[0]
                .previous_account_status
                == "suspended"
            )
            assert (
                events[0].new_account_status
                == "active"
            )

    after_stores = await store_snapshot(
        sessions,
        fixture["seller_id"],
    )

    assert after_stores == before_stores


@pytest.mark.parametrize(
    (
        "label",
        "initial_active",
        "first_action",
        "second_action",
        "expected_action",
        "expected_active",
        "allowed_conflicts",
    ),
    [
        pytest.param(
            "double-suspend",
            True,
            "suspend",
            "suspend",
            "suspend",
            False,
            {
                (
                    "Seller account changed. "
                    "Refresh and try again."
                ),
            },
            id="simultaneous-suspend",
        ),
        pytest.param(
            "double-reactivate",
            False,
            "reactivate",
            "reactivate",
            "reactivate",
            True,
            {
                (
                    "Seller account changed. "
                    "Refresh and try again."
                ),
            },
            id="simultaneous-reactivate",
        ),
        pytest.param(
            "active-cross",
            True,
            "suspend",
            "reactivate",
            "suspend",
            False,
            {
                "Seller account is already active.",
                (
                    "Seller account changed. "
                    "Refresh and try again."
                ),
            },
            id="active-cross-action",
        ),
        pytest.param(
            "suspended-cross",
            False,
            "suspend",
            "reactivate",
            "reactivate",
            True,
            {
                (
                    "Seller account is already "
                    "suspended."
                ),
                (
                    "Seller account changed. "
                    "Refresh and try again."
                ),
            },
            id="suspended-cross-action",
        ),
    ],
)
@pytest.mark.asyncio
async def test_account_action_race_has_one_winner(
    test_database,
    label,
    initial_active,
    first_action,
    second_action,
    expected_action,
    expected_active,
    allowed_conflicts,
):
    _engine, sessions = test_database

    fixture = await create_fixture(
        sessions,
        label=label,
        is_active=initial_active,
    )

    try:
        before_stores = await store_snapshot(
            sessions,
            fixture["seller_id"],
        )

        common = {
            "seller_id": fixture["seller_id"],
            "admin_id": fixture["admin_id"],
            "expected_updated_at": (
                fixture["updated_at"]
            ),
        }

        results = await execute_race(
            sessions,
            {
                **common,
                "action_name": first_action,
                "reason": (
                    f"Concurrent {first_action} A"
                ),
            },
            {
                **common,
                "action_name": second_action,
                "reason": (
                    f"Concurrent {second_action} B"
                ),
            },
        )

        assert_one_winner(
            results,
            expected_action=expected_action,
            allowed_conflicts=allowed_conflicts,
        )

        await verify_final_state(
            sessions,
            fixture=fixture,
            expected_active=expected_active,
            expected_action=expected_action,
            before_stores=before_stores,
        )

    finally:
        await cleanup_fixture(
            sessions,
            fixture,
        )
