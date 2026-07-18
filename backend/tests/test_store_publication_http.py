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
from app.core.security import (
    create_access_token,
)
from app.db.session import get_db
from app.models import (
    Product,
    Store,
    StorePublicationEvent,
    User,
)


EXPECTED_ALEMBIC_HEAD = "f0a2b4d6e8c1"

STORE_RESPONSE_FIELDS = {
    "id",
    "owner_id",
    "slug",
    "name",
    "bio",
    "logo_url",
    "banner_url",
    "whatsapp_number",
    "social_links",
    "category",
    "theme",
    "is_active",
    "is_suspended",
    "publication_status",
    "plan_name",
    "subscription_status",
    "trial_ends_at",
    "subscription_ends_at",
    "last_payment_at",
    "monthly_fee",
    "created_at",
    "updated_at",
}


def validated_test_database_url() -> URL:
    raw_url = os.environ.get(
        "TEST_DATABASE_URL",
        "",
    ).strip()

    if not raw_url:
        pytest.skip(
            "TEST_DATABASE_URL is not "
            "configured."
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
            "HTTP integration tests require "
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
        admin = User(
            email=(
                "publication-http-admin-"
                f"{suffix}@example.com"
            ),
            full_name="HTTP Publication Admin",
            password_hash="admin-test-hash",
            role="platform_admin",
            is_active=True,
            is_verified=True,
        )

        seller = User(
            email=(
                "publication-http-seller-"
                f"{suffix}@example.com"
            ),
            full_name="HTTP Publication Seller",
            password_hash="seller-test-hash",
            role="merchant",
            is_active=True,
            is_verified=True,
        )

        staff = User(
            email=(
                "publication-http-staff-"
                f"{suffix}@example.com"
            ),
            full_name="HTTP Non-Platform Staff",
            password_hash="staff-test-hash",
            role="support",
            is_active=True,
            is_verified=True,
        )

        session.add_all(
            [
                admin,
                seller,
                staff,
            ]
        )

        await session.flush()

        store = Store(
            owner_id=seller.id,
            slug=(
                "publication-http-"
                f"{suffix}"
            ),
            name="HTTP Publication Store",
            bio="HTTP authorization fixture",
            logo_url=None,
            banner_url=None,
            whatsapp_number=None,
            social_links={},
            category="testing",
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
            last_payment_at=None,
            monthly_fee=Decimal("0.00"),
            updated_at=(
                now - timedelta(minutes=5)
            ),
        )

        session.add(store)
        await session.flush()

        product = Product(
            store_id=store.id,
            name="HTTP Active Product",
            slug=(
                "http-active-product-"
                f"{suffix}"
            ),
            description=(
                "Publication HTTP fixture"
            ),
            image_url=None,
            product_type="physical",
            price=Decimal("100.00"),
            stock_quantity=5,
            is_active=True,
            is_featured=False,
        )

        session.add(product)
        await session.commit()

        return {
            "admin_id": admin.id,
            "seller_id": seller.id,
            "staff_id": staff.id,
            "store_id": store.id,
            "product_id": product.id,
            "updated_at": store.updated_at,
            "admin_token": create_access_token(
                str(admin.id),
                admin.role,
            ),
            "seller_token": create_access_token(
                str(seller.id),
                seller.role,
            ),
            "staff_token": create_access_token(
                str(staff.id),
                staff.role,
            ),
        }


async def cleanup_fixture_rows(
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
                StorePublicationEvent.store_id
                == fixture["store_id"]
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
                User.id.in_(
                    [
                        fixture["admin_id"],
                        fixture["seller_id"],
                        fixture["staff_id"],
                    ]
                )
            )
        )

        await session.commit()


@pytest_asyncio.fixture
async def publication_http_fixture():
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


def publication_url(
    fixture: dict,
    action: str,
    *,
    store_id=None,
) -> str:
    target_store_id = (
        store_id
        if store_id is not None
        else fixture["store_id"]
    )

    return (
        "/api/v1/admin/stores/"
        f"{target_store_id}/{action}"
    )


def bearer_headers(token: str) -> dict:
    return {
        "Authorization": (
            f"Bearer {token}"
        )
    }


def publication_payload(
    updated_at,
    *,
    reason: str | None = None,
) -> dict:
    payload = {
        "expected_updated_at": (
            updated_at.isoformat()
            if hasattr(
                updated_at,
                "isoformat",
            )
            else updated_at
        )
    }

    if reason is not None:
        payload["reason"] = reason

    return payload


@pytest.mark.parametrize(
    "action",
    [
        "publish",
        "unpublish",
    ],
)
async def test_publication_requires_authentication(
    publication_http_fixture,
    action,
):
    fixture = publication_http_fixture

    response = await fixture[
        "client"
    ].post(
        publication_url(
            fixture,
            action,
        ),
        json=publication_payload(
            fixture["updated_at"]
        ),
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Not authenticated."
    }


@pytest.mark.parametrize(
    "action",
    [
        "publish",
        "unpublish",
    ],
)
async def test_publication_rejects_seller_token(
    publication_http_fixture,
    action,
):
    fixture = publication_http_fixture

    response = await fixture[
        "client"
    ].post(
        publication_url(
            fixture,
            action,
        ),
        headers=bearer_headers(
            fixture["seller_token"]
        ),
        json=publication_payload(
            fixture["updated_at"]
        ),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Platform admin access required."
        )
    }


@pytest.mark.parametrize(
    "action",
    [
        "publish",
        "unpublish",
    ],
)
async def test_publication_rejects_non_platform_staff(
    publication_http_fixture,
    action,
):
    fixture = publication_http_fixture

    response = await fixture[
        "client"
    ].post(
        publication_url(
            fixture,
            action,
        ),
        headers=bearer_headers(
            fixture["staff_token"]
        ),
        json=publication_payload(
            fixture["updated_at"]
        ),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Platform admin access required."
        )
    }


async def test_admin_publish_and_unpublish_http_contract(
    publication_http_fixture,
):
    fixture = publication_http_fixture
    client = fixture["client"]

    publish_response = await client.post(
        publication_url(
            fixture,
            "publish",
        ),
        headers=bearer_headers(
            fixture["admin_token"]
        ),
        json=publication_payload(
            fixture["updated_at"],
            reason=(
                "  HTTP publication proof  "
            ),
        ),
    )

    assert publish_response.status_code == 200

    published = publish_response.json()

    assert set(published) == (
        STORE_RESPONSE_FIELDS
    )
    assert published["id"] == str(
        fixture["store_id"]
    )
    assert published["owner_id"] == str(
        fixture["seller_id"]
    )
    assert (
        published["publication_status"]
        == "published"
    )

    unpublish_response = await client.post(
        publication_url(
            fixture,
            "unpublish",
        ),
        headers=bearer_headers(
            fixture["admin_token"]
        ),
        json=publication_payload(
            published["updated_at"],
            reason="HTTP unpublish proof",
        ),
    )

    assert (
        unpublish_response.status_code
        == 200
    )

    unpublished = unpublish_response.json()

    assert set(unpublished) == (
        STORE_RESPONSE_FIELDS
    )
    assert (
        unpublished[
            "publication_status"
        ]
        == "draft"
    )

    async with fixture[
        "sessions"
    ]() as session:
        result = await session.execute(
            select(
                StorePublicationEvent
            )
            .where(
                (
                    StorePublicationEvent
                    .store_id
                )
                == fixture["store_id"]
            )
            .order_by(
                (
                    StorePublicationEvent
                    .created_at
                ).asc(),
                (
                    StorePublicationEvent
                    .id
                ).asc(),
            )
        )

        events = list(
            result.scalars().all()
        )

    assert len(events) == 2

    publish_event = events[0]
    unpublish_event = events[1]

    assert publish_event.actor_user_id == (
        fixture["admin_id"]
    )
    assert (
        publish_event.actor_role
        == "platform_admin"
    )
    assert publish_event.action == "publish"
    assert (
        publish_event
        .previous_publication_status
        == "draft"
    )
    assert (
        publish_event
        .new_publication_status
        == "published"
    )
    assert (
        publish_event.reason
        == "HTTP publication proof"
    )
    assert isinstance(
        publish_event.readiness_snapshot,
        dict,
    )
    assert (
        publish_event
        .readiness_snapshot[
            "active_product_count"
        ]
        == 1
    )

    assert (
        unpublish_event.action
        == "unpublish"
    )
    assert (
        unpublish_event
        .previous_publication_status
        == "published"
    )
    assert (
        unpublish_event
        .new_publication_status
        == "draft"
    )
    assert (
        unpublish_event.reason
        == "HTTP unpublish proof"
    )


async def test_admin_missing_store_returns_safe_404(
    publication_http_fixture,
):
    fixture = publication_http_fixture

    response = await fixture[
        "client"
    ].post(
        publication_url(
            fixture,
            "publish",
            store_id=uuid.uuid4(),
        ),
        headers=bearer_headers(
            fixture["admin_token"]
        ),
        json=publication_payload(
            fixture["updated_at"]
        ),
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Store not found."
    }
