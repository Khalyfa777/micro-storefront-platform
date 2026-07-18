import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.v1.router import api_router
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import (
    Order,
    OrderItem,
    Product,
    ProductOrderField,
    ProductOrderFieldOption,
    Store,
    User,
)
from app.schemas.order import OrderItemCreate


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
            "Safety stop: expected "
            "storefront_platform_test."
        )

    if (
        url.drivername
        != "postgresql+asyncpg"
    ):
        pytest.fail(
            "Order-integrity tests require "
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
                "order-integrity-seller-"
                f"{suffix}@example.com"
            ),
            full_name=(
                "Order Integrity Seller"
            ),
            password_hash=(
                "order-integrity-test-hash"
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
                "order-integrity-"
                f"{suffix}"
            ),
            name="Order Integrity Store",
            bio="Order integrity fixture",
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

        configured_product = Product(
            store_id=store.id,
            name="Configured Sneakers",
            slug=(
                "configured-sneakers-"
                f"{suffix}"
            ),
            description=(
                "Order integrity product"
            ),
            image_url=None,
            product_type="physical",
            default_fulfillment_method=(
                "delivery"
            ),
            allowed_fulfillment_methods=[
                "delivery",
                "pickup",
            ],
            price=Decimal("100.00"),
            stock_quantity=10,
            is_active=True,
            is_featured=False,
        )
        plain_product = Product(
            store_id=store.id,
            name="Plain Product",
            slug=(
                "plain-product-"
                f"{suffix}"
            ),
            description=(
                "Second lock-order product"
            ),
            image_url=None,
            product_type="physical",
            default_fulfillment_method=(
                "delivery"
            ),
            allowed_fulfillment_methods=[
                "delivery",
                "pickup",
            ],
            price=Decimal("50.00"),
            stock_quantity=10,
            is_active=True,
            is_featured=False,
        )
        confirmation_product = Product(
            store_id=store.id,
            name="Confirmed Product",
            slug=(
                "confirmed-product-"
                f"{suffix}"
            ),
            description=(
                "Required confirmation fixture"
            ),
            image_url=None,
            product_type="physical",
            default_fulfillment_method=(
                "pickup"
            ),
            allowed_fulfillment_methods=[
                "pickup",
            ],
            price=Decimal("75.00"),
            stock_quantity=10,
            is_active=True,
            is_featured=False,
        )
        service_product = Product(
            store_id=store.id,
            name="On-site Service",
            slug=(
                "on-site-service-"
                f"{suffix}"
            ),
            description=(
                "Service location fixture"
            ),
            image_url=None,
            product_type="service",
            default_fulfillment_method=(
                "on_site_service"
            ),
            allowed_fulfillment_methods=[
                "on_site_service",
                "remote_service",
            ],
            price=Decimal("200.00"),
            stock_quantity=None,
            is_active=True,
            is_featured=False,
        )
        session.add_all(
            [
                configured_product,
                plain_product,
                confirmation_product,
                service_product,
            ]
        )
        await session.flush()

        confirmation_field = ProductOrderField(
            product_id=confirmation_product.id,
            key="terms_confirmed",
            label="Confirm the order terms",
            field_type="checkbox",
            placeholder=None,
            help_text=None,
            is_required=True,
            is_sensitive=False,
            include_in_whatsapp=True,
            is_active=True,
            sort_order=0,
            validation_rules={},
        )
        session.add(confirmation_field)

        order_field = ProductOrderField(
            product_id=configured_product.id,
            key="shoe_size",
            label="Shoe size",
            field_type="select",
            placeholder=None,
            help_text=None,
            is_required=True,
            is_sensitive=False,
            include_in_whatsapp=True,
            is_active=True,
            sort_order=0,
            validation_rules={},
        )
        session.add(order_field)
        await session.flush()

        session.add_all(
            [
                ProductOrderFieldOption(
                    field_id=order_field.id,
                    value="44",
                    label="44",
                    price_adjustment=Decimal(
                        "0.00"
                    ),
                    is_active=True,
                    sort_order=0,
                ),
                ProductOrderFieldOption(
                    field_id=order_field.id,
                    value="45",
                    label="45",
                    price_adjustment=Decimal(
                        "10.00"
                    ),
                    is_active=True,
                    sort_order=1,
                ),
            ]
        )

        await session.commit()

        return {
            "seller_id": seller.id,
            "store_id": store.id,
            "store_slug": store.slug,
            "configured_product_id": (
                configured_product.id
            ),
            "plain_product_id": (
                plain_product.id
            ),
            "confirmation_product_id": (
                confirmation_product.id
            ),
            "service_product_id": (
                service_product.id
            ),
            "seller_token": (
                create_access_token(
                    str(seller.id),
                    seller.role,
                )
            ),
        }


async def cleanup_fixture_rows(
    sessions: async_sessionmaker[
        AsyncSession
    ],
    fixture: dict,
) -> None:
    async with sessions() as session:
        order_ids = list(
            (
                await session.scalars(
                    select(Order.id).where(
                        Order.store_id
                        == fixture["store_id"]
                    )
                )
            ).all()
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
                User.id
                == fixture["seller_id"]
            )
        )
        await session.commit()


@pytest_asyncio.fixture
async def order_integrity_http_fixture():
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
            app=test_app,
            raise_app_exceptions=False,
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


def new_idempotency_key() -> str:
    return (
        "order-integrity-"
        f"{uuid.uuid4()}"
    )


def auth_headers(
    fixture: dict,
) -> dict[str, str]:
    return {
        "Authorization": (
            "Bearer "
            f"{fixture['seller_token']}"
        )
    }


def configured_item(
    fixture: dict,
    *,
    size: str,
    quantity: int,
) -> dict:
    return {
        "product_id": str(
            fixture[
                "configured_product_id"
            ]
        ),
        "quantity": quantity,
        "selected_options": {
            "shoe_size": size,
        },
    }


def plain_item(
    fixture: dict,
    *,
    quantity: int,
) -> dict:
    return {
        "product_id": str(
            fixture["plain_product_id"]
        ),
        "quantity": quantity,
        "selected_options": {},
    }


def confirmation_item(
    fixture: dict,
    *,
    confirmed: bool,
    quantity: int = 1,
) -> dict:
    return {
        "product_id": str(
            fixture[
                "confirmation_product_id"
            ]
        ),
        "quantity": quantity,
        "selected_options": {
            "terms_confirmed": confirmed,
        },
    }


def service_item(
    fixture: dict,
    *,
    quantity: int = 1,
) -> dict:
    return {
        "product_id": str(
            fixture["service_product_id"]
        ),
        "quantity": quantity,
        "selected_options": {},
    }


def order_payload(
    fixture: dict,
    *,
    items: list[dict],
    fulfillment_method: str = "delivery",
    delivery_address: str | None = (
        "Accra test address"
    ),
) -> dict:
    return {
        "store_slug": fixture["store_slug"],
        "customer_name": (
            "Order Integrity Customer"
        ),
        "customer_phone": "0241234567",
        "customer_email": (
            "integrity@example.com"
        ),
        "delivery_address": delivery_address,
        "customer_note": None,
        "fulfillment_method": fulfillment_method,
        "handoff_channel": "none",
        "items": items,
    }


async def create_order(
    fixture: dict,
    *,
    items: list[dict],
):
    return await fixture["client"].post(
        "/api/v1/public/orders",
        headers={
            "Idempotency-Key": (
                new_idempotency_key()
            )
        },
        json=order_payload(
            fixture,
            items=items,
        ),
    )


async def set_product_stock(
    fixture: dict,
    product_id,
    quantity: int,
) -> None:
    async with fixture[
        "sessions"
    ]() as session:
        product = await session.get(
            Product,
            product_id,
        )
        assert product is not None
        product.stock_quantity = quantity
        await session.commit()


async def load_product_stock(
    fixture: dict,
    product_id,
) -> int | None:
    async with fixture[
        "sessions"
    ]() as session:
        product = await session.get(
            Product,
            product_id,
        )
        assert product is not None
        return product.stock_quantity


async def count_orders(
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


def test_selected_options_normalize_scalar_numbers():
    item = OrderItemCreate.model_validate(
        {
            "product_id": (
                "00000000-0000-0000-"
                "0000-000000000001"
            ),
            "quantity": 1,
            "selected_options": {
                "guest_count": 4.0,
                "confirmed": True,
            },
        }
    )

    assert item.selected_options == {
        "guest_count": "4.0",
        "confirmed": True,
    }


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("customer_email", 123),
        (
            "delivery_address",
            {"city": "Accra"},
        ),
        ("customer_note", False),
    ],
)
@pytest.mark.asyncio
async def test_non_text_optional_order_fields_are_rejected(
    order_integrity_http_fixture,
    field_name,
    invalid_value,
):
    fixture = order_integrity_http_fixture
    payload = order_payload(
        fixture,
        items=[
            configured_item(
                fixture,
                size="44",
                quantity=1,
            )
        ],
    )
    payload[field_name] = invalid_value

    response = await fixture["client"].post(
        "/api/v1/public/orders",
        headers={
            "Idempotency-Key": (
                new_idempotency_key()
            )
        },
        json=payload,
    )

    assert response.status_code == 422
    assert await count_orders(fixture) == 0


@pytest.mark.asyncio
async def test_nested_selected_options_are_rejected(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture
    response = await fixture["client"].post(
        "/api/v1/public/orders",
        headers={
            "Idempotency-Key": (
                new_idempotency_key()
            )
        },
        json=order_payload(
            fixture,
            items=[
                {
                    "product_id": str(
                        fixture[
                            "configured_product_id"
                        ]
                    ),
                    "quantity": 1,
                    "selected_options": {
                        "shoe_size": {
                            "items": ["44"]
                        }
                    },
                }
            ],
        ),
    )

    assert response.status_code == 422
    assert await count_orders(fixture) == 0


@pytest.mark.asyncio
async def test_required_confirmation_checkbox_false_is_rejected(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture

    response = await fixture["client"].post(
        "/api/v1/public/orders",
        headers={
            "Idempotency-Key": (
                new_idempotency_key()
            )
        },
        json=order_payload(
            fixture,
            items=[
                confirmation_item(
                    fixture,
                    confirmed=False,
                )
            ],
            fulfillment_method="pickup",
            delivery_address=None,
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Confirm the order terms must be confirmed."
    )
    assert await count_orders(fixture) == 0


@pytest.mark.asyncio
async def test_required_confirmation_checkbox_true_is_accepted(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture

    response = await fixture["client"].post(
        "/api/v1/public/orders",
        headers={
            "Idempotency-Key": (
                new_idempotency_key()
            )
        },
        json=order_payload(
            fixture,
            items=[
                confirmation_item(
                    fixture,
                    confirmed=True,
                )
            ],
            fulfillment_method="pickup",
            delivery_address=None,
        ),
    )

    assert response.status_code == 200
    assert (
        response.json()["items"][0][
            "selected_options"
        ]["terms_confirmed"]
        is True
    )


@pytest.mark.asyncio
async def test_delivery_order_requires_location(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture

    response = await fixture["client"].post(
        "/api/v1/public/orders",
        headers={
            "Idempotency-Key": (
                new_idempotency_key()
            )
        },
        json=order_payload(
            fixture,
            items=[
                configured_item(
                    fixture,
                    size="44",
                    quantity=1,
                )
            ],
            fulfillment_method="delivery",
            delivery_address="   ",
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Delivery location is required."
    )
    assert await count_orders(fixture) == 0


@pytest.mark.asyncio
async def test_on_site_service_requires_location(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture

    response = await fixture["client"].post(
        "/api/v1/public/orders",
        headers={
            "Idempotency-Key": (
                new_idempotency_key()
            )
        },
        json=order_payload(
            fixture,
            items=[
                service_item(fixture)
            ],
            fulfillment_method=(
                "on_site_service"
            ),
            delivery_address=None,
        ),
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Service location is required."
    )
    assert await count_orders(fixture) == 0


@pytest.mark.asyncio
async def test_pickup_discards_stale_location(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture

    response = await fixture["client"].post(
        "/api/v1/public/orders",
        headers={
            "Idempotency-Key": (
                new_idempotency_key()
            )
        },
        json=order_payload(
            fixture,
            items=[
                configured_item(
                    fixture,
                    size="44",
                    quantity=1,
                )
            ],
            fulfillment_method="pickup",
            delivery_address=(
                "Stale hidden location"
            ),
        ),
    )

    assert response.status_code == 200
    assert response.json()[
        "delivery_address"
    ] is None


@pytest.mark.asyncio
async def test_remote_service_discards_stale_location(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture

    response = await fixture["client"].post(
        "/api/v1/public/orders",
        headers={
            "Idempotency-Key": (
                new_idempotency_key()
            )
        },
        json=order_payload(
            fixture,
            items=[
                service_item(fixture)
            ],
            fulfillment_method=(
                "remote_service"
            ),
            delivery_address=(
                "Stale hidden location"
            ),
        ),
    )

    assert response.status_code == 200
    assert response.json()[
        "delivery_address"
    ] is None


@pytest.mark.asyncio
async def test_create_aggregates_duplicate_product_stock(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture
    await set_product_stock(
        fixture,
        fixture["configured_product_id"],
        5,
    )

    response = await create_order(
        fixture,
        items=[
            configured_item(
                fixture,
                size="44",
                quantity=3,
            ),
            configured_item(
                fixture,
                size="45",
                quantity=3,
            ),
        ],
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Only 5 left in stock for "
        "Configured Sneakers"
    )
    assert await count_orders(fixture) == 0


@pytest.mark.asyncio
async def test_split_lines_remain_separate_and_deduct_aggregate_stock(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture

    created = await create_order(
        fixture,
        items=[
            configured_item(
                fixture,
                size="44",
                quantity=2,
            ),
            configured_item(
                fixture,
                size="45",
                quantity=1,
            ),
        ],
    )

    assert created.status_code == 200
    body = created.json()
    assert len(body["items"]) == 2
    assert Decimal(
        str(body["subtotal"])
    ) == Decimal("310.00")
    assert {
        item["selected_options"][
            "shoe_size"
        ]
        for item in body["items"]
    } == {"44", "45"}

    paid = await fixture["client"].patch(
        (
            f"/api/v1/stores/"
            f"{fixture['store_id']}/orders/"
            f"{body['id']}/status"
        ),
        headers=auth_headers(fixture),
        json={"status": "paid"},
    )

    assert paid.status_code == 200
    assert paid.json()[
        "inventory_deducted"
    ] is True
    assert (
        await load_product_stock(
            fixture,
            fixture[
                "configured_product_id"
            ],
        )
        == 7
    )


@pytest.mark.asyncio
async def test_paid_transition_rolls_back_when_aggregate_stock_is_short(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture
    created = await create_order(
        fixture,
        items=[
            configured_item(
                fixture,
                size="44",
                quantity=2,
            ),
            configured_item(
                fixture,
                size="45",
                quantity=2,
            ),
        ],
    )

    assert created.status_code == 200
    order_id = created.json()["id"]

    await set_product_stock(
        fixture,
        fixture["configured_product_id"],
        3,
    )

    paid = await fixture["client"].patch(
        (
            f"/api/v1/stores/"
            f"{fixture['store_id']}/orders/"
            f"{order_id}/status"
        ),
        headers=auth_headers(fixture),
        json={"status": "paid"},
    )

    assert paid.status_code == 400
    assert (
        await load_product_stock(
            fixture,
            fixture[
                "configured_product_id"
            ],
        )
        == 3
    )

    async with fixture[
        "sessions"
    ]() as session:
        order = await session.get(
            Order,
            uuid.UUID(order_id),
        )

    assert order is not None
    assert order.status == "pending"
    assert order.inventory_deducted is False


@pytest.mark.asyncio
async def test_order_waits_for_product_configuration_transaction(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture

    async with fixture[
        "sessions"
    ]() as session:
        await session.execute(
            select(Product)
            .where(
                Product.id
                == fixture[
                    "configured_product_id"
                ]
            )
            .with_for_update()
        )
        option = await session.scalar(
            select(
                ProductOrderFieldOption
            )
            .join(ProductOrderField)
            .where(
                ProductOrderField.product_id
                == fixture[
                    "configured_product_id"
                ],
                ProductOrderFieldOption.value
                == "44",
            )
        )
        assert option is not None

        option.label = "EU 44 updated"
        option.price_adjustment = (
            Decimal("25.00")
        )
        await session.flush()

        request_task = asyncio.create_task(
            create_order(
                fixture,
                items=[
                    configured_item(
                        fixture,
                        size="44",
                        quantity=1,
                    )
                ],
            )
        )

        await asyncio.sleep(0.2)
        request_was_blocked = (
            not request_task.done()
        )

        await session.commit()
        response = await asyncio.wait_for(
            request_task,
            timeout=5,
        )

    assert request_was_blocked is True
    assert response.status_code == 200

    item = response.json()["items"][0]
    assert Decimal(
        str(item["unit_price"])
    ) == Decimal("125.00")
    assert item[
        "configuration_snapshot"
    ][0]["display_value"] == (
        "EU 44 updated"
    )


@pytest.mark.asyncio
async def test_concurrent_paid_orders_lock_products_in_one_order(
    order_integrity_http_fixture,
):
    fixture = order_integrity_http_fixture

    first = await create_order(
        fixture,
        items=[
            configured_item(
                fixture,
                size="44",
                quantity=1,
            ),
            plain_item(
                fixture,
                quantity=1,
            ),
        ],
    )
    second = await create_order(
        fixture,
        items=[
            plain_item(
                fixture,
                quantity=1,
            ),
            configured_item(
                fixture,
                size="45",
                quantity=1,
            ),
        ],
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_transport = ASGITransport(
        app=fixture["app"],
        raise_app_exceptions=False,
    )
    second_transport = ASGITransport(
        app=fixture["app"],
        raise_app_exceptions=False,
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
        responses = await asyncio.wait_for(
            asyncio.gather(
                first_client.patch(
                    (
                        f"/api/v1/stores/"
                        f"{fixture['store_id']}"
                        f"/orders/"
                        f"{first.json()['id']}"
                        "/status"
                    ),
                    headers=auth_headers(
                        fixture
                    ),
                    json={"status": "paid"},
                ),
                second_client.patch(
                    (
                        f"/api/v1/stores/"
                        f"{fixture['store_id']}"
                        f"/orders/"
                        f"{second.json()['id']}"
                        "/status"
                    ),
                    headers=auth_headers(
                        fixture
                    ),
                    json={"status": "paid"},
                ),
            ),
            timeout=10,
        )

    assert sorted(
        response.status_code
        for response in responses
    ) == [200, 200]

    assert (
        await load_product_stock(
            fixture,
            fixture[
                "configured_product_id"
            ],
        )
        == 8
    )
    assert (
        await load_product_stock(
            fixture,
            fixture["plain_product_id"],
        )
        == 8
    )
