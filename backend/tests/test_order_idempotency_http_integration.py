import asyncio
import os
import uuid
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import (
    ASGITransport,
    AsyncClient,
)
from sqlalchemy import (
    delete,
    func,
    select,
    text,
)
from sqlalchemy.engine import (
    URL,
    make_url,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.v1.router import api_router
from app.db.session import get_db
from app.models import (
    Order,
    OrderItem,
    Product,
    Store,
    User,
)


EXPECTED_ALEMBIC_HEAD = "f0a2b4d6e8c1"


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
            "disposable "
            "storefront_platform_test "
            "database."
        )

    if (
        url.drivername
        != "postgresql+asyncpg"
    ):
        pytest.fail(
            "Order idempotency integration "
            "tests require "
            "postgresql+asyncpg."
        )

    return url


async def create_fixture_rows(
    sessions: async_sessionmaker[
        AsyncSession
    ],
) -> dict:
    suffix = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)

    async with sessions() as session:
        seller = User(
            email=(
                "order-idempotency-seller-"
                f"{suffix}@example.com"
            ),
            full_name=(
                "Order Idempotency Seller"
            ),
            password_hash=(
                "order-idempotency-test-hash"
            ),
            role="merchant",
            is_active=True,
            is_verified=True,
        )

        session.add(seller)
        await session.flush()

        store = Store(
            owner_id=seller.id,
            slug=(
                "order-idempotency-"
                f"{suffix}"
            ),
            name=(
                "Order Idempotency Store"
            ),
            bio=(
                "Real HTTP and PostgreSQL "
                "idempotency fixture"
            ),
            logo_url=None,
            banner_url=None,
            whatsapp_number=None,
            social_links={},
            category="testing",
            theme="default",
            is_active=True,
            is_suspended=False,
            publication_status="published",
            plan_name="business",
            subscription_status="trial",
            trial_ends_at=(
                now + timedelta(days=14)
            ),
            subscription_ends_at=None,
            last_payment_at=None,
            monthly_fee=Decimal("0.00"),
        )

        session.add(store)
        await session.flush()

        product = Product(
            store_id=store.id,
            name=(
                "Concurrent Order Product"
            ),
            slug=(
                "concurrent-order-product-"
                f"{suffix}"
            ),
            description=(
                "Idempotency integration "
                "test product"
            ),
            image_url=None,
            product_type="physical",
            price=Decimal("125.00"),
            stock_quantity=10,
            is_active=True,
            is_featured=False,
        )

        session.add(product)
        await session.commit()

        return {
            "seller_id": seller.id,
            "store_id": store.id,
            "store_slug": store.slug,
            "product_id": product.id,
        }


async def cleanup_fixture_rows(
    sessions: async_sessionmaker[
        AsyncSession
    ],
    fixture: dict,
) -> None:
    async with sessions() as session:
        order_ids_result = (
            await session.execute(
                select(Order.id).where(
                    Order.store_id
                    == fixture["store_id"]
                )
            )
        )

        order_ids = list(
            order_ids_result.scalars().all()
        )

        if order_ids:
            await session.execute(
                delete(OrderItem).where(
                    OrderItem.order_id.in_(
                        order_ids
                    )
                )
            )

            await session.execute(
                delete(Order).where(
                    Order.id.in_(order_ids)
                )
            )

        await session.execute(
            delete(Product).where(
                Product.id
                == fixture["product_id"]
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
                User.id
                == fixture["seller_id"]
            )
        )

        await session.commit()


@pytest_asyncio.fixture
async def order_http_fixture():
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

    fixture = None
    test_app = FastAPI()

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
        assert revision == EXPECTED_ALEMBIC_HEAD

        fixture = await create_fixture_rows(
            sessions
        )

        test_app.include_router(api_router)

        async def override_get_db():
            async with sessions() as session:
                yield session

        test_app.dependency_overrides[
            get_db
        ] = override_get_db

        transport = ASGITransport(
            app=test_app
        )

        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield {
                **fixture,
                "app": test_app,
                "client": client,
                "sessions": sessions,
            }

    finally:
        test_app.dependency_overrides.clear()

        if fixture is not None:
            await cleanup_fixture_rows(
                sessions,
                fixture,
            )

        await engine.dispose()


def make_order_payload(
    fixture: dict,
    *,
    quantity: int = 1,
) -> dict:
    return {
        "store_slug": fixture["store_slug"],
        "customer_name": (
            "Concurrent Customer"
        ),
        "customer_phone": "0241234567",
        "customer_email": (
            "concurrent@example.com"
        ),
        "delivery_address": (
            "Accra test address"
        ),
        "customer_note": (
            "Idempotency integration test"
        ),
        "items": [
            {
                "product_id": str(
                    fixture["product_id"]
                ),
                "quantity": quantity,
            }
        ],
    }


def idempotency_headers(
    key: str,
) -> dict:
    return {
        "Idempotency-Key": key,
    }


def new_idempotency_key() -> str:
    return (
        "order-http-"
        f"{uuid.uuid4()}"
    )


async def count_fixture_orders(
    fixture: dict,
) -> int:
    async with fixture[
        "sessions"
    ]() as session:
        count = await session.scalar(
            select(
                func.count(Order.id)
            ).where(
                Order.store_id
                == fixture["store_id"]
            )
        )

    return int(count or 0)


async def load_fixture_orders(
    fixture: dict,
) -> list[Order]:
    async with fixture[
        "sessions"
    ]() as session:
        result = await session.execute(
            select(Order)
            .where(
                Order.store_id
                == fixture["store_id"]
            )
            .order_by(Order.created_at.asc())
        )

        return list(
            result.scalars().all()
        )


async def test_missing_idempotency_header_is_rejected(
    order_http_fixture,
):
    fixture = order_http_fixture

    response = await fixture[
        "client"
    ].post(
        "/api/v1/public/orders",
        json=make_order_payload(fixture),
    )

    assert response.status_code == 400

    assert response.json() == {
        "detail": (
            "Idempotency-Key header is "
            "required."
        )
    }

    assert (
        await count_fixture_orders(fixture)
        == 0
    )


async def test_matching_retry_replays_original_order(
    order_http_fixture,
):
    fixture = order_http_fixture
    key = new_idempotency_key()
    payload = make_order_payload(fixture)

    first = await fixture[
        "client"
    ].post(
        "/api/v1/public/orders",
        headers=idempotency_headers(key),
        json=payload,
    )

    second = await fixture[
        "client"
    ].post(
        "/api/v1/public/orders",
        headers=idempotency_headers(key),
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_data = first.json()
    second_data = second.json()

    assert (
        first_data["id"]
        == second_data["id"]
    )

    assert (
        first_data["order_number"]
        == second_data["order_number"]
    )

    assert (
        await count_fixture_orders(fixture)
        == 1
    )

    orders = await load_fixture_orders(
        fixture
    )

    assert orders[0].idempotency_key == key
    assert (
        len(
            orders[0].request_fingerprint
            or ""
        )
        == 64
    )


async def test_reused_key_with_changed_payload_conflicts(
    order_http_fixture,
):
    fixture = order_http_fixture
    key = new_idempotency_key()

    first = await fixture[
        "client"
    ].post(
        "/api/v1/public/orders",
        headers=idempotency_headers(key),
        json=make_order_payload(
            fixture,
            quantity=1,
        ),
    )

    conflict = await fixture[
        "client"
    ].post(
        "/api/v1/public/orders",
        headers=idempotency_headers(key),
        json=make_order_payload(
            fixture,
            quantity=2,
        ),
    )

    assert first.status_code == 200
    assert conflict.status_code == 409

    assert conflict.json() == {
        "detail": (
            "This Idempotency-Key was "
            "already used with different "
            "order details."
        )
    }

    assert (
        await count_fixture_orders(fixture)
        == 1
    )


async def test_concurrent_matching_requests_create_one_order(
    order_http_fixture,
):
    fixture = order_http_fixture
    key = new_idempotency_key()
    payload = make_order_payload(fixture)

    first_transport = ASGITransport(
        app=fixture["app"]
    )

    second_transport = ASGITransport(
        app=fixture["app"]
    )

    async with (
        AsyncClient(
            transport=first_transport,
            base_url="http://testserver",
        ) as first_client,
        AsyncClient(
            transport=second_transport,
            base_url="http://testserver",
        ) as second_client,
    ):
        first_response, second_response = (
            await asyncio.gather(
                first_client.post(
                    "/api/v1/public/orders",
                    headers=(
                        idempotency_headers(key)
                    ),
                    json=payload,
                ),
                second_client.post(
                    "/api/v1/public/orders",
                    headers=(
                        idempotency_headers(key)
                    ),
                    json=payload,
                ),
            )
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_data = first_response.json()
    second_data = second_response.json()

    assert (
        first_data["id"]
        == second_data["id"]
    )

    assert (
        first_data["order_number"]
        == second_data["order_number"]
    )

    assert (
        await count_fixture_orders(fixture)
        == 1
    )


async def test_concurrent_mismatched_requests_create_one_order(
    order_http_fixture,
):
    fixture = order_http_fixture
    key = new_idempotency_key()

    first_transport = ASGITransport(
        app=fixture["app"]
    )

    second_transport = ASGITransport(
        app=fixture["app"]
    )

    async with (
        AsyncClient(
            transport=first_transport,
            base_url="http://testserver",
        ) as first_client,
        AsyncClient(
            transport=second_transport,
            base_url="http://testserver",
        ) as second_client,
    ):
        responses = await asyncio.gather(
            first_client.post(
                "/api/v1/public/orders",
                headers=(
                    idempotency_headers(key)
                ),
                json=make_order_payload(
                    fixture,
                    quantity=1,
                ),
            ),
            second_client.post(
                "/api/v1/public/orders",
                headers=(
                    idempotency_headers(key)
                ),
                json=make_order_payload(
                    fixture,
                    quantity=2,
                ),
            ),
        )

    status_codes = sorted(
        response.status_code
        for response in responses
    )

    assert status_codes == [200, 409]

    assert (
        await count_fixture_orders(fixture)
        == 1
    )
