import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.v1.products import update_product
from app.api.v1.store_publication import (
    AdminStorePublicationRequest,
    publish_store,
)
from app.models import (
    Product,
    Store,
    StorePublicationEvent,
    User,
)
from app.schemas.product import ProductUpdate


EXPECTED_ALEMBIC_HEAD = "e3a5c7d9f1b2"
TIMEOUT_SECONDS = 10


class PausedCommitSession(AsyncSession):
    def __init__(
        self,
        *args,
        commit_started: asyncio.Event,
        release_commit: asyncio.Event,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._commit_started = commit_started
        self._release_commit = release_commit

    async def commit(self) -> None:
        self._commit_started.set()

        await asyncio.wait_for(
            self._release_commit.wait(),
            timeout=TIMEOUT_SECONDS,
        )

        await super().commit()


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

    if (
        url.database
        != "storefront_platform_test"
    ):
        pytest.fail(
            "Safety stop: expected the "
            "disposable storefront_platform_test "
            "database."
        )

    if (
        url.drivername
        != "postgresql+asyncpg"
    ):
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
            database_name = (
                await connection.scalar(
                    text(
                        "SELECT current_database()"
                    )
                )
            )

            revision = (
                await connection.scalar(
                    text(
                        "SELECT version_num "
                        "FROM alembic_version"
                    )
                )
            )

        assert database_name == url.database
        assert (
            revision
            == EXPECTED_ALEMBIC_HEAD
        )

        yield engine, sessions

    finally:
        await engine.dispose()


async def create_fixture(
    sessions: async_sessionmaker[
        AsyncSession
    ],
    *,
    label: str,
) -> dict:
    suffix = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)

    async with sessions() as session:
        admin = User(
            email=(
                f"publication-admin-{label}-"
                f"{suffix}@example.com"
            ),
            full_name="Publication Admin",
            password_hash=(
                "admin-test-hash"
            ),
            role="platform_admin",
            is_active=True,
            is_verified=True,
        )

        seller = User(
            email=(
                f"publication-seller-{label}-"
                f"{suffix}@example.com"
            ),
            full_name="Publication Seller",
            password_hash=(
                "seller-test-hash"
            ),
            role="merchant",
            is_active=True,
            is_verified=True,
        )

        session.add_all(
            [admin, seller]
        )

        await session.flush()

        store = Store(
            owner_id=seller.id,
            slug=(
                f"publication-{label}-"
                f"{suffix}"
            ),
            name=(
                "Publication Concurrency Store"
            ),
            social_links={},
            theme="default",
            is_active=True,
            is_suspended=False,
            publication_status="draft",
            plan_name="business",
            subscription_status="trial",
            trial_ends_at=(
                now + timedelta(days=14)
            ),
            subscription_ends_at=None,
            monthly_fee=Decimal("0.00"),
            updated_at=(
                now - timedelta(minutes=5)
            ),
        )

        session.add(store)
        await session.flush()

        product = Product(
            store_id=store.id,
            name="Only Active Product",
            slug=(
                f"only-product-{suffix}"
            ),
            description=(
                "Concurrency fixture"
            ),
            image_url=None,
            product_type="physical",
            price=Decimal("100.00"),
            stock_quantity=2,
            is_active=True,
            is_featured=False,
        )

        session.add(product)
        await session.commit()

        return {
            "admin_id": admin.id,
            "seller_id": seller.id,
            "store_id": store.id,
            "product_id": product.id,
            "updated_at": store.updated_at,
        }


async def cleanup_fixture(
    sessions: async_sessionmaker[
        AsyncSession
    ],
    fixture: dict,
) -> None:
    async with sessions() as session:
        await session.execute(
            delete(
                StorePublicationEvent
            ).where(
                (
                    StorePublicationEvent
                    .store_id
                )
                == fixture["store_id"]
            )
        )

        await session.execute(
            delete(Product).where(
                Product.store_id
                == fixture["store_id"]
            )
        )

        await session.execute(
            delete(Store).where(
                Store.id
                == fixture["store_id"]
            )
        )

        await session.execute(
            delete(User).where(
                User.id.in_(
                    [
                        fixture[
                            "seller_id"
                        ],
                        fixture[
                            "admin_id"
                        ],
                    ]
                )
            )
        )

        await session.commit()


async def wait_until_lock_wait(
    sessions: async_sessionmaker[
        AsyncSession
    ],
    backend_pid: int,
) -> str:
    loop = asyncio.get_running_loop()

    deadline = (
        loop.time()
        + TIMEOUT_SECONDS
    )

    async with sessions() as observer:
        while loop.time() < deadline:
            row = (
                await observer.execute(
                    text(
                        "SELECT "
                        "wait_event_type, "
                        "wait_event "
                        "FROM pg_stat_activity "
                        "WHERE pid = :pid"
                    ),
                    {
                        "pid": backend_pid
                    },
                )
            ).one_or_none()

            if (
                row is not None
                and row.wait_event_type
                == "Lock"
            ):
                return (
                    row.wait_event
                    or "Lock"
                )

            await asyncio.sleep(0.05)

    raise AssertionError(
        "Competing PostgreSQL session "
        "did not enter a lock wait."
    )


async def run_operation(
    *,
    operation: str,
    engine: AsyncEngine,
    fixture: dict,
    pid_future: asyncio.Future,
    commit_started: (
        asyncio.Event | None
    ) = None,
    release_commit: (
        asyncio.Event | None
    ) = None,
) -> tuple[str, object]:
    if (
        commit_started is not None
        and release_commit is not None
    ):
        session = PausedCommitSession(
            bind=engine,
            expire_on_commit=False,
            commit_started=commit_started,
            release_commit=release_commit,
        )
    else:
        session = AsyncSession(
            bind=engine,
            expire_on_commit=False,
        )

    async with session:
        backend_pid = (
            await session.scalar(
                text(
                    "SELECT pg_backend_pid()"
                )
            )
        )

        pid_future.set_result(
            backend_pid
        )

        try:
            if operation == "publish":
                result = await publish_store(
                    store_id=(
                        fixture["store_id"]
                    ),
                    payload=(
                        AdminStorePublicationRequest(
                            expected_updated_at=(
                                fixture[
                                    "updated_at"
                                ]
                            ),
                            reason=(
                                "Concurrency "
                                "verification"
                            ),
                        )
                    ),
                    current_admin=(
                        SimpleNamespace(
                            id=(
                                fixture[
                                    "admin_id"
                                ]
                            ),
                            role=(
                                "platform_admin"
                            ),
                        )
                    ),
                    db=session,
                )

            elif operation == "deactivate":
                result = await update_product(
                    product_id=(
                        fixture[
                            "product_id"
                        ]
                    ),
                    payload=ProductUpdate(
                        is_active=False
                    ),
                    store=SimpleNamespace(
                        id=(
                            fixture[
                                "store_id"
                            ]
                        )
                    ),
                    db=session,
                )

            else:
                raise AssertionError(
                    "Unknown operation: "
                    f"{operation}"
                )

        except HTTPException as exc:
            await session.rollback()

            return (
                "http_error",
                exc,
            )

        return "ok", result


async def read_final_state(
    sessions: async_sessionmaker[
        AsyncSession
    ],
    fixture: dict,
) -> dict:
    async with sessions() as session:
        store = await session.get(
            Store,
            fixture["store_id"],
        )

        product = await session.get(
            Product,
            fixture["product_id"],
        )

        events = list(
            (
                await session.scalars(
                    select(
                        StorePublicationEvent
                    )
                    .where(
                        (
                            StorePublicationEvent
                            .store_id
                        )
                        == fixture[
                            "store_id"
                        ]
                    )
                    .order_by(
                        (
                            StorePublicationEvent
                            .created_at
                        ),
                        (
                            StorePublicationEvent
                            .id
                        ),
                    )
                )
            ).all()
        )

        return {
            "publication_status": (
                store.publication_status
            ),
            "product_is_active": (
                product.is_active
            ),
            "events": events,
        }


async def cancel_tasks(
    *tasks: asyncio.Task | None,
) -> None:
    pending = [
        task
        for task in tasks
        if task is not None
        and not task.done()
    ]

    for task in pending:
        task.cancel()

    if pending:
        await asyncio.gather(
            *pending,
            return_exceptions=True,
        )


@pytest.mark.parametrize(
    "first_operation",
    [
        "deactivate",
        "publish",
    ],
)
@pytest.mark.asyncio
async def test_publication_product_race_preserves_invariant(
    test_database,
    first_operation,
):
    engine, sessions = test_database

    fixture = await create_fixture(
        sessions,
        label=first_operation,
    )

    second_operation = (
        "publish"
        if first_operation
        == "deactivate"
        else "deactivate"
    )

    release_first = asyncio.Event()
    first_at_commit = asyncio.Event()

    loop = asyncio.get_running_loop()

    first_pid = loop.create_future()
    second_pid = loop.create_future()

    first_task = None
    second_task = None

    try:
        first_task = asyncio.create_task(
            run_operation(
                operation=first_operation,
                engine=engine,
                fixture=fixture,
                pid_future=first_pid,
                commit_started=(
                    first_at_commit
                ),
                release_commit=(
                    release_first
                ),
            )
        )

        await asyncio.wait_for(
            first_at_commit.wait(),
            timeout=TIMEOUT_SECONDS,
        )

        second_task = asyncio.create_task(
            run_operation(
                operation=second_operation,
                engine=engine,
                fixture=fixture,
                pid_future=second_pid,
            )
        )

        second_backend_pid = (
            await asyncio.wait_for(
                second_pid,
                timeout=TIMEOUT_SECONDS,
            )
        )

        lock_event = (
            await wait_until_lock_wait(
                sessions,
                second_backend_pid,
            )
        )

        assert lock_event

        release_first.set()

        first_result, second_result = (
            await asyncio.wait_for(
                asyncio.gather(
                    first_task,
                    second_task,
                ),
                timeout=TIMEOUT_SECONDS,
            )
        )

        final_state = (
            await read_final_state(
                sessions,
                fixture,
            )
        )

        assert first_result[0] == "ok"

        assert (
            second_result[0]
            == "http_error"
        )

        second_error = second_result[1]

        assert (
            second_error.status_code
            == 409
        )

        if (
            first_operation
            == "deactivate"
        ):
            assert (
                "At least one active product"
                in str(
                    second_error.detail
                )
            )

            assert (
                final_state[
                    "publication_status"
                ]
                == "draft"
            )

            assert (
                final_state[
                    "product_is_active"
                ]
                is False
            )

            assert (
                final_state["events"]
                == []
            )

        else:
            assert (
                "last active product"
                in str(
                    second_error.detail
                )
            )

            assert (
                final_state[
                    "publication_status"
                ]
                == "published"
            )

            assert (
                final_state[
                    "product_is_active"
                ]
                is True
            )

            assert (
                len(
                    final_state["events"]
                )
                == 1
            )

            event = (
                final_state["events"][0]
            )

            assert (
                event.action
                == "publish"
            )

            assert (
                event
                .previous_publication_status
                == "draft"
            )

            assert (
                event
                .new_publication_status
                == "published"
            )

    finally:
        release_first.set()

        await cancel_tasks(
            first_task,
            second_task,
        )

        await cleanup_fixture(
            sessions,
            fixture,
        )


class StoreUpdateThenFailEventSession(
    AsyncSession
):
    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            *args,
            **kwargs,
        )

        self.store_update_flushed_before_failure = (
            False
        )

    async def flush(
        self,
        objects=None,
    ) -> None:
        pending_events = [
            value
            for value in self.new
            if isinstance(
                value,
                StorePublicationEvent,
            )
        ]

        if not pending_events:
            await super().flush(objects)
            return

        dirty_stores = [
            value
            for value in self.dirty
            if isinstance(value, Store)
        ]

        if len(dirty_stores) != 1:
            raise AssertionError(
                "Expected exactly one dirty store "
                "before the forced event failure."
            )

        if (
            dirty_stores[0].publication_status
            != "published"
        ):
            raise AssertionError(
                "Store was not changed to "
                "published before event insertion."
            )

        for event in pending_events:
            self.expunge(event)

        # Send the store UPDATE to PostgreSQL
        # without committing it.
        await super().flush()

        self.store_update_flushed_before_failure = (
            True
        )

        # Re-add the event with an action that
        # violates the PostgreSQL check constraint.
        for event in pending_events:
            event.action = (
                "invalid"
            )
            self.add(event)

        await super().flush()


@pytest.mark.asyncio
async def test_real_event_insert_failure_rolls_back_store_change(
    test_database,
):
    engine, sessions = test_database

    fixture = await create_fixture(
        sessions,
        label="event-rollback",
    )

    failure_sessions = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=StoreUpdateThenFailEventSession,
    )

    try:
        async with failure_sessions() as session:
            admin = await session.get(
                User,
                fixture["admin_id"],
            )

            assert admin is not None

            with pytest.raises(
                IntegrityError
            ) as exc_info:
                await publish_store(
                    store_id=fixture[
                        "store_id"
                    ],
                    payload=(
                        AdminStorePublicationRequest(
                            expected_updated_at=(
                                fixture[
                                    "updated_at"
                                ]
                            ),
                            reason=(
                                "Forced PostgreSQL "
                                "rollback proof"
                            ),
                        )
                    ),
                    current_admin=admin,
                    db=session,
                )

            assert (
                getattr(
                    exc_info.value.orig,
                    "sqlstate",
                    None,
                )
                == "23514"
            )

            assert (
                session
                .store_update_flushed_before_failure
                is True
            )

        async with sessions() as session:
            store = await session.get(
                Store,
                fixture["store_id"],
            )

            event_result = await session.execute(
                select(
                    StorePublicationEvent
                ).where(
                    (
                        StorePublicationEvent
                        .store_id
                    )
                    == fixture["store_id"]
                )
            )

            events = list(
                event_result.scalars().all()
            )

        assert store is not None

        assert (
            store.publication_status
            == "draft"
        )

        assert (
            store.updated_at
            == fixture["updated_at"]
        )

        assert events == []

    finally:
        await cleanup_fixture(
            sessions,
            fixture,
        )
