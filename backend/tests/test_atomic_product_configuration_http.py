import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import selectinload

from app.api.v1 import products as products_api
from app.api.v1.router import api_router
from app.core.security import create_access_token
from app.db.session import get_db
from app.models import (
    Product,
    ProductOrderField,
    ProductOrderFieldOption,
    Store,
    User,
)


EXPECTED_ALEMBIC_HEAD = "f0a2b4d6e8c1"


def validated_test_database_url() -> URL:
    raw_url = os.environ.get("TEST_DATABASE_URL", "").strip()

    if not raw_url:
        pytest.skip("TEST_DATABASE_URL is not configured.")

    url = make_url(raw_url)

    if url.database != "storefront_platform_test":
        pytest.fail(
            "Safety stop: expected storefront_platform_test."
        )

    if url.drivername != "postgresql+asyncpg":
        pytest.fail(
            "Atomic product tests require postgresql+asyncpg."
        )

    return url


def order_fields_payload(*, size_value: str = "44") -> list[dict]:
    return [
        {
            "key": "shoe_size",
            "label": "Shoe size",
            "field_type": "select",
            "placeholder": None,
            "help_text": "Choose the size you want.",
            "is_required": True,
            "is_sensitive": False,
            "include_in_whatsapp": True,
            "is_active": True,
            "sort_order": 0,
            "validation_rules": {},
            "options": [
                {
                    "value": size_value,
                    "label": size_value,
                    "price_adjustment": "0.00",
                    "is_active": True,
                    "sort_order": 0,
                }
            ],
        }
    ]


def prohibited_prompt_fields(
    *,
    placeholder: str | None = None,
    help_text: str | None = None,
) -> list[dict]:
    return [
        {
            "key": "account_details",
            "label": "Account details",
            "field_type": "text",
            "placeholder": placeholder,
            "help_text": help_text,
            "is_required": False,
            "is_sensitive": False,
            "include_in_whatsapp": True,
            "is_active": True,
            "sort_order": 0,
            "validation_rules": {},
            "options": [],
        }
    ]


def product_payload(
    *,
    slug: str,
    name: str = "Atomic Sneakers",
    size_value: str = "44",
) -> dict:
    return {
        "name": name,
        "slug": slug,
        "description": "Atomic product configuration test.",
        "image_url": None,
        "product_type": "physical",
        "default_fulfillment_method": "delivery",
        "allowed_fulfillment_methods": [
            "delivery",
            "pickup",
        ],
        "price": "300.00",
        "stock_quantity": 10,
        "is_active": True,
        "is_featured": False,
        "order_fields": order_fields_payload(
            size_value=size_value,
        ),
    }


async def create_fixture_rows(
    sessions: async_sessionmaker[AsyncSession],
) -> dict:
    suffix = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)

    async with sessions() as session:
        seller = User(
            email=f"atomic-seller-{suffix}@example.com",
            full_name="Atomic Seller",
            password_hash="atomic-seller-test-hash",
            role="merchant",
            is_active=True,
            is_verified=True,
        )
        other_seller = User(
            email=f"atomic-other-{suffix}@example.com",
            full_name="Atomic Other Seller",
            password_hash="atomic-other-test-hash",
            role="merchant",
            is_active=True,
            is_verified=True,
        )
        session.add_all([seller, other_seller])
        await session.flush()

        store = Store(
            owner_id=seller.id,
            slug=f"atomic-store-{suffix}",
            name="Atomic Store",
            bio="Atomic save fixture",
            social_links={},
            category="testing",
            theme="default",
            is_active=True,
            is_suspended=False,
            publication_status="published",
            plan_name="business",
            subscription_status="trial",
            trial_ends_at=now + timedelta(days=14),
            monthly_fee=Decimal("0.00"),
        )
        other_store = Store(
            owner_id=other_seller.id,
            slug=f"atomic-other-store-{suffix}",
            name="Atomic Other Store",
            bio="Tenant isolation fixture",
            social_links={},
            category="testing",
            theme="default",
            is_active=True,
            is_suspended=False,
            publication_status="draft",
            plan_name="business",
            subscription_status="trial",
            trial_ends_at=now + timedelta(days=14),
            monthly_fee=Decimal("0.00"),
        )
        session.add_all([store, other_store])
        await session.flush()

        product = Product(
            store_id=store.id,
            name="Original Sneakers",
            slug=f"original-sneakers-{suffix}",
            description="Original configuration",
            image_url=None,
            product_type="physical",
            default_fulfillment_method="delivery",
            allowed_fulfillment_methods=[
                "delivery",
                "pickup",
            ],
            price=Decimal("250.00"),
            stock_quantity=5,
            is_active=True,
            is_featured=False,
        )
        session.add(product)
        await session.flush()

        order_field = ProductOrderField(
            product_id=product.id,
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
        session.add(
            ProductOrderFieldOption(
                field_id=order_field.id,
                value="41",
                label="41",
                price_adjustment=Decimal("0.00"),
                is_active=True,
                sort_order=0,
            )
        )

        await session.commit()

        return {
            "seller_id": seller.id,
            "other_seller_id": other_seller.id,
            "store_id": store.id,
            "other_store_id": other_store.id,
            "product_id": product.id,
            "seller_token": create_access_token(
                str(seller.id),
                seller.role,
            ),
            "other_token": create_access_token(
                str(other_seller.id),
                other_seller.role,
            ),
        }


async def cleanup_fixture_rows(
    sessions: async_sessionmaker[AsyncSession],
    fixture: dict,
) -> None:
    async with sessions() as session:
        await session.execute(
            delete(Product).where(
                Product.store_id.in_(
                    [
                        fixture["store_id"],
                        fixture["other_store_id"],
                    ]
                )
            )
        )
        await session.execute(
            delete(Store).where(
                Store.id.in_(
                    [
                        fixture["store_id"],
                        fixture["other_store_id"],
                    ]
                )
            )
        )
        await session.execute(
            delete(User).where(
                User.id.in_(
                    [
                        fixture["seller_id"],
                        fixture["other_seller_id"],
                    ]
                )
            )
        )
        await session.commit()


@pytest_asyncio.fixture
async def atomic_product_http_fixture():
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
            database_name = await connection.scalar(
                text("SELECT current_database()")
            )
            revision = await connection.scalar(
                text(
                    "SELECT version_num "
                    "FROM alembic_version"
                )
            )

        assert database_name == url.database
        assert revision == EXPECTED_ALEMBIC_HEAD

        fixture = await create_fixture_rows(sessions)
        test_app.include_router(api_router)

        async def override_get_db():
            async with sessions() as session:
                yield session

        test_app.dependency_overrides[get_db] = override_get_db

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


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
    }


async def load_product(
    fixture: dict,
    product_id,
) -> Product | None:
    async with fixture["sessions"]() as session:
        result = await session.execute(
            select(Product)
            .options(
                selectinload(Product.order_fields).selectinload(
                    ProductOrderField.options
                )
            )
            .where(Product.id == product_id)
        )
        return result.scalar_one_or_none()


@pytest.mark.asyncio
async def test_atomic_create_persists_product_and_fields(
    atomic_product_http_fixture,
):
    fixture = atomic_product_http_fixture
    slug = f"atomic-created-{uuid.uuid4().hex[:10]}"

    response = await fixture["client"].post(
        f"/api/v1/stores/{fixture['store_id']}/products",
        headers=auth_headers(fixture["seller_token"]),
        json=product_payload(slug=slug),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == slug
    assert body["order_fields"][0]["key"] == "shoe_size"
    assert (
        body["order_fields"][0]["options"][0]["value"]
        == "44"
    )

    stored = await load_product(fixture, body["id"])
    assert stored is not None
    assert stored.name == "Atomic Sneakers"
    assert stored.order_fields[0].options[0].value == "44"


@pytest.mark.asyncio
async def test_atomic_update_persists_product_and_fields_together(
    atomic_product_http_fixture,
):
    fixture = atomic_product_http_fixture

    response = await fixture["client"].patch(
        (
            f"/api/v1/stores/{fixture['store_id']}"
            f"/products/{fixture['product_id']}"
        ),
        headers=auth_headers(fixture["seller_token"]),
        json={
            "name": "Updated Sneakers",
            "price": "320.00",
            "order_fields": order_fields_payload(
                size_value="45",
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated Sneakers"
    assert Decimal(str(body["price"])) == Decimal("320.00")
    assert (
        body["order_fields"][0]["options"][0]["value"]
        == "45"
    )

    stored = await load_product(
        fixture,
        fixture["product_id"],
    )
    assert stored is not None
    assert stored.name == "Updated Sneakers"
    assert stored.price == Decimal("320.00")
    assert stored.order_fields[0].options[0].value == "45"


@pytest.mark.asyncio
async def test_atomic_create_rejects_empty_fulfillment_list(
    atomic_product_http_fixture,
):
    fixture = atomic_product_http_fixture
    slug = (
        "empty-fulfillment-"
        f"{uuid.uuid4().hex[:10]}"
    )
    payload = product_payload(slug=slug)
    payload["allowed_fulfillment_methods"] = []

    response = await fixture["client"].post(
        f"/api/v1/stores/{fixture['store_id']}/products",
        headers=auth_headers(
            fixture["seller_token"]
        ),
        json=payload,
    )

    assert response.status_code == 422
    assert (
        "At least one fulfilment method is required"
        in response.text
    )

    async with fixture[
        "sessions"
    ]() as session:
        stored = await session.scalar(
            select(Product).where(
                Product.store_id
                == fixture["store_id"],
                Product.slug == slug,
            )
        )

    assert stored is None


@pytest.mark.asyncio
async def test_atomic_create_rejects_prohibited_placeholder(
    atomic_product_http_fixture,
):
    fixture = atomic_product_http_fixture
    slug = (
        "unsafe-placeholder-"
        f"{uuid.uuid4().hex[:10]}"
    )
    payload = product_payload(slug=slug)
    payload["order_fields"] = (
        prohibited_prompt_fields(
            placeholder="Enter your password",
        )
    )

    response = await fixture["client"].post(
        f"/api/v1/stores/{fixture['store_id']}/products",
        headers=auth_headers(
            fixture["seller_token"]
        ),
        json=payload,
    )

    assert response.status_code == 422
    assert (
        "prohibited credential"
        in response.text.lower()
    )

    async with fixture[
        "sessions"
    ]() as session:
        stored = await session.scalar(
            select(Product).where(
                Product.store_id
                == fixture["store_id"],
                Product.slug == slug,
            )
        )

    assert stored is None


@pytest.mark.asyncio
async def test_atomic_update_rejects_prohibited_help_text(
    atomic_product_http_fixture,
):
    fixture = atomic_product_http_fixture

    response = await fixture["client"].patch(
        (
            f"/api/v1/stores/{fixture['store_id']}"
            f"/products/{fixture['product_id']}"
        ),
        headers=auth_headers(
            fixture["seller_token"]
        ),
        json={
            "name": "Must Stay Original",
            "order_fields": (
                prohibited_prompt_fields(
                    help_text=(
                        "Enter the OTP sent "
                        "to your phone"
                    ),
                )
            ),
        },
    )

    assert response.status_code == 422
    assert (
        "prohibited credential"
        in response.text.lower()
    )

    stored = await load_product(
        fixture,
        fixture["product_id"],
    )
    assert stored is not None
    assert stored.name == "Original Sneakers"
    assert (
        stored.order_fields[0]
        .options[0]
        .value
        == "41"
    )


@pytest.mark.asyncio
async def test_atomic_create_rejects_card_details_help_text(
    atomic_product_http_fixture,
):
    fixture = atomic_product_http_fixture
    slug = (
        "unsafe-card-details-"
        f"{uuid.uuid4().hex[:10]}"
    )
    payload = product_payload(slug=slug)
    payload["order_fields"] = (
        prohibited_prompt_fields(
            help_text=(
                "Enter your card details"
            ),
        )
    )

    response = await fixture["client"].post(
        f"/api/v1/stores/{fixture['store_id']}/products",
        headers=auth_headers(
            fixture["seller_token"]
        ),
        json=payload,
    )

    assert response.status_code == 422
    assert (
        "prohibited credential"
        in response.text.lower()
    )

    async with fixture[
        "sessions"
    ]() as session:
        stored = await session.scalar(
            select(Product).where(
                Product.store_id
                == fixture["store_id"],
                Product.slug == slug,
            )
        )

    assert stored is None


@pytest.mark.asyncio
async def test_atomic_create_rolls_back_when_field_write_fails(
    atomic_product_http_fixture,
    monkeypatch,
):
    fixture = atomic_product_http_fixture
    slug = f"atomic-failed-create-{uuid.uuid4().hex[:10]}"

    async def fail_field_write(*args, **kwargs):
        raise RuntimeError("forced field-write failure")

    monkeypatch.setattr(
        products_api,
        "_replace_product_order_fields_in_transaction",
        fail_field_write,
    )

    response = await fixture["client"].post(
        f"/api/v1/stores/{fixture['store_id']}/products",
        headers=auth_headers(fixture["seller_token"]),
        json=product_payload(slug=slug),
    )

    assert response.status_code == 500

    async with fixture["sessions"]() as session:
        stored = await session.scalar(
            select(Product).where(
                Product.store_id == fixture["store_id"],
                Product.slug == slug,
            )
        )

    assert stored is None


@pytest.mark.asyncio
async def test_atomic_update_rolls_back_both_sides_on_failure(
    atomic_product_http_fixture,
    monkeypatch,
):
    fixture = atomic_product_http_fixture

    async def fail_field_write(*args, **kwargs):
        raise RuntimeError("forced field-write failure")

    monkeypatch.setattr(
        products_api,
        "_replace_product_order_fields_in_transaction",
        fail_field_write,
    )

    response = await fixture["client"].patch(
        (
            f"/api/v1/stores/{fixture['store_id']}"
            f"/products/{fixture['product_id']}"
        ),
        headers=auth_headers(fixture["seller_token"]),
        json={
            "name": "Must Roll Back",
            "price": "999.00",
            "order_fields": order_fields_payload(
                size_value="46",
            ),
        },
    )

    assert response.status_code == 500

    stored = await load_product(
        fixture,
        fixture["product_id"],
    )
    assert stored is not None
    assert stored.name == "Original Sneakers"
    assert stored.price == Decimal("250.00")
    assert stored.order_fields[0].options[0].value == "41"


@pytest.mark.asyncio
async def test_atomic_update_preserves_tenant_isolation(
    atomic_product_http_fixture,
):
    fixture = atomic_product_http_fixture

    response = await fixture["client"].patch(
        (
            f"/api/v1/stores/{fixture['other_store_id']}"
            f"/products/{fixture['product_id']}"
        ),
        headers=auth_headers(fixture["other_token"]),
        json={
            "name": "Cross-tenant update",
            "order_fields": order_fields_payload(
                size_value="47",
            ),
        },
    )

    assert response.status_code == 404

    stored = await load_product(
        fixture,
        fixture["product_id"],
    )
    assert stored is not None
    assert stored.name == "Original Sneakers"
    assert stored.order_fields[0].options[0].value == "41"
