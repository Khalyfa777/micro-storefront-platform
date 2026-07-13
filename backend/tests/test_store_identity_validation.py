from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.store import (
    StoreCreate,
    StoreUpdate,
)
from app.services.store_publication import (
    get_admin_publish_blockers,
)


def valid_store():
    now = datetime.now(timezone.utc)

    return SimpleNamespace(
        name="Valid Store",
        slug="valid-store",
        publication_status="draft",
        is_active=True,
        is_suspended=False,
        subscription_status="trial",
        trial_ends_at=(
            now + timedelta(days=14)
        ),
        subscription_ends_at=None,
    )


def valid_owner():
    return SimpleNamespace(
        role="merchant",
        is_verified=True,
        password_hash="accepted",
    )


def test_store_create_accepts_canonical_identity():
    payload = StoreCreate(
        name="  Valid Store  ",
        slug="valid-store",
    )

    assert payload.name == "Valid Store"
    assert payload.slug == "valid-store"


@pytest.mark.parametrize(
    "slug",
    [
        "My-Store",
        "my store",
        "my--store",
        "-my-store",
        "my-store-",
        "ab",
        "admin",
        "track",
        "payment",
    ],
)
def test_store_create_rejects_invalid_slug(
    slug,
):
    with pytest.raises(ValidationError):
        StoreCreate(
            name="Valid Store",
            slug=slug,
        )


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "Invalid\nStore",
        "x" * 256,
    ],
)
def test_store_create_rejects_invalid_name(
    name,
):
    with pytest.raises(ValidationError):
        StoreCreate(
            name=name,
            slug="valid-store",
        )


def test_store_update_rejects_null_identity():
    with pytest.raises(ValidationError):
        StoreUpdate(slug=None)

    with pytest.raises(ValidationError):
        StoreUpdate(name=None)


def test_store_update_allows_unrelated_fields():
    payload = StoreUpdate(
        bio="Updated bio"
    )

    assert payload.bio == "Updated bio"


def test_publication_blocks_invalid_legacy_slug():
    store = valid_store()
    store.slug = "Invalid Store Slug"

    blockers = get_admin_publish_blockers(
        store=store,
        owner=valid_owner(),
        active_product_count=1,
    )

    assert (
        "Store slug is invalid."
        in blockers
    )


def test_publication_blocks_reserved_legacy_slug():
    store = valid_store()
    store.slug = "track"

    blockers = get_admin_publish_blockers(
        store=store,
        owner=valid_owner(),
        active_product_count=1,
    )

    assert (
        "Store slug is invalid."
        in blockers
    )


def test_publication_blocks_invalid_legacy_name():
    store = valid_store()
    store.name = "Invalid\nStore"

    blockers = get_admin_publish_blockers(
        store=store,
        owner=valid_owner(),
        active_product_count=1,
    )

    assert (
        "Store name is invalid."
        in blockers
    )
