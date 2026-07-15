import io
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.middleware.request_body_limit import (
    RequestBodyLimitMiddleware,
)
from app.services import image_upload
from app.services.image_validation import (
    validate_uploaded_image_safety,
)


def make_png_bytes() -> bytes:
    output = io.BytesIO()

    image = Image.new(
        "RGB",
        (8, 8),
        color=(20, 40, 60),
    )

    image.save(
        output,
        format="PNG",
    )

    return output.getvalue()


def make_upload(
    image_bytes: bytes,
    content_type: str = "image/png",
) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(image_bytes),
        filename="test.png",
        headers=Headers(
            {
                "content-type": (
                    content_type
                ),
            }
        ),
    )


def test_image_validation_accepts_matching_png():
    extension = (
        validate_uploaded_image_safety(
            make_png_bytes(),
            "image/png",
        )
    )

    assert extension == ".png"


def test_image_validation_rejects_mime_mismatch():
    with pytest.raises(
        HTTPException
    ) as captured:
        validate_uploaded_image_safety(
            make_png_bytes(),
            "image/jpeg",
        )

    assert captured.value.status_code == 400
    assert (
        "does not match"
        in captured.value.detail
    )


@pytest.mark.asyncio
async def test_streamed_upload_rejects_oversize(
    monkeypatch,
):
    monkeypatch.setattr(
        image_upload.settings,
        "IMAGE_UPLOAD_MAX_BYTES",
        16,
    )

    upload = make_upload(
        b"x" * 17
    )

    with pytest.raises(
        HTTPException
    ) as captured:
        await (
            image_upload
            .read_and_validate_image_upload(
                upload
            )
        )

    assert captured.value.status_code == 413


def test_atomic_write_replaces_destination(
    tmp_path: Path,
):
    destination = (
        tmp_path
        / "image.png"
    )

    destination.write_bytes(
        b"old"
    )

    image_upload._atomic_write_sync(
        destination,
        b"new",
    )

    assert (
        destination.read_bytes()
        == b"new"
    )

    assert list(
        tmp_path.glob("*.tmp")
    ) == []


def test_orphan_cleanup_preserves_referenced_and_recent(
    monkeypatch,
    tmp_path: Path,
):
    store_id = uuid4()
    upload_root = (
        tmp_path
        / "static"
        / "uploads"
    )
    product_dir = (
        upload_root
        / "products"
    )
    logo_dir = (
        upload_root
        / "stores"
        / "logos"
    )
    banner_dir = (
        upload_root
        / "stores"
        / "banners"
    )

    for directory in (
        product_dir,
        logo_dir,
        banner_dir,
    ):
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    monkeypatch.setattr(
        image_upload,
        "_UPLOAD_DIRECTORIES",
        {
            "product": product_dir,
            "logo": logo_dir,
            "banner": banner_dir,
        },
    )

    monkeypatch.setattr(
        image_upload,
        "_PROJECT_ROOT",
        tmp_path,
    )

    monkeypatch.setattr(
        image_upload,
        "UPLOAD_ROOT",
        upload_root,
    )

    monkeypatch.setattr(
        image_upload.settings,
        "BACKEND_PUBLIC_URL",
        "https://api.storeplughq.com",
    )

    monkeypatch.setattr(
        image_upload.settings,
        "IMAGE_UPLOAD_ORPHAN_TTL_SECONDS",
        60,
    )

    referenced = (
        product_dir
        / f"{store_id}-referenced.png"
    )
    orphaned = (
        product_dir
        / f"{store_id}-orphaned.png"
    )
    recent = (
        product_dir
        / f"{store_id}-recent.png"
    )

    for path in (
        referenced,
        orphaned,
        recent,
    ):
        path.write_bytes(b"image")

    old_timestamp = (
        os.path.getmtime(orphaned)
        - 120
    )

    os.utime(
        referenced,
        (
            old_timestamp,
            old_timestamp,
        ),
    )
    os.utime(
        orphaned,
        (
            old_timestamp,
            old_timestamp,
        ),
    )

    referenced_url = (
        "https://api.storeplughq.com/"
        + referenced.relative_to(
            tmp_path
        ).as_posix()
    )

    image_upload._cleanup_orphaned_files_sync(
        store_id,
        {referenced_url},
    )

    assert referenced.exists()
    assert not orphaned.exists()
    assert recent.exists()


@pytest.mark.asyncio
async def test_request_body_limit_rejects_content_length():
    app_called = False
    sent_messages = []

    async def app(
        scope,
        receive,
        send,
    ):
        nonlocal app_called
        app_called = True

    middleware = (
        RequestBodyLimitMiddleware(
            app,
            max_body_bytes=4,
        )
    )

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/upload",
        "headers": [
            (
                b"content-length",
                b"5",
            ),
        ],
    }

    async def receive():
        return {
            "type": "http.request",
            "body": b"",
            "more_body": False,
        }

    async def send(message):
        sent_messages.append(message)

    await middleware(
        scope,
        receive,
        send,
    )

    assert app_called is False
    assert (
        sent_messages[0]["status"]
        == 413
    )


@pytest.mark.asyncio
async def test_request_body_limit_counts_streamed_body():
    sent_messages = []
    receive_count = 0

    async def app(
        scope,
        receive,
        send,
    ):
        while True:
            message = await receive()

            if not message.get(
                "more_body",
                False,
            ):
                break

    middleware = (
        RequestBodyLimitMiddleware(
            app,
            max_body_bytes=4,
        )
    )

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/upload",
        "headers": [],
    }

    async def receive():
        nonlocal receive_count
        receive_count += 1

        return {
            "type": "http.request",
            "body": b"12345",
            "more_body": False,
        }

    async def send(message):
        sent_messages.append(message)

    await middleware(
        scope,
        receive,
        send,
    )

    assert receive_count == 1
    assert (
        sent_messages[0]["status"]
        == 413
    )

def _configure_temporary_upload_root(
    monkeypatch,
    tmp_path: Path,
):
    upload_root = (
        tmp_path
        / "static"
        / "uploads"
    )
    product_dir = (
        upload_root
        / "products"
    )
    logo_dir = (
        upload_root
        / "stores"
        / "logos"
    )
    banner_dir = (
        upload_root
        / "stores"
        / "banners"
    )

    for directory in (
        product_dir,
        logo_dir,
        banner_dir,
    ):
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    monkeypatch.setattr(
        image_upload,
        "_PROJECT_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        image_upload,
        "UPLOAD_ROOT",
        upload_root,
    )
    monkeypatch.setattr(
        image_upload,
        "_UPLOAD_DIRECTORIES",
        {
            "product": product_dir,
            "logo": logo_dir,
            "banner": banner_dir,
        },
    )

    return (
        upload_root,
        product_dir,
        logo_dir,
        banner_dir,
    )


def test_generated_managed_image_url_is_portable(
    monkeypatch,
    tmp_path: Path,
):
    (
        _,
        product_dir,
        _,
        _,
    ) = _configure_temporary_upload_root(
        monkeypatch,
        tmp_path,
    )

    destination = (
        product_dir
        / "image.png"
    )

    assert (
        image_upload
        ._public_url_for_path(
            destination
        )
        == "/static/uploads/products/image.png"
    )


def test_relative_managed_image_reference_resolves(
    monkeypatch,
    tmp_path: Path,
):
    store_id = uuid4()
    (
        _,
        product_dir,
        _,
        _,
    ) = _configure_temporary_upload_root(
        monkeypatch,
        tmp_path,
    )

    destination = (
        product_dir
        / f"{store_id}-relative.png"
    )

    resolved = (
        image_upload
        ._managed_path_from_url(
            (
                "/static/uploads/products/"
                + destination.name
            ),
            store_id,
        )
    )

    assert resolved == destination.resolve()


def test_legacy_private_managed_image_reference_resolves(
    monkeypatch,
    tmp_path: Path,
):
    store_id = uuid4()
    (
        _,
        product_dir,
        _,
        _,
    ) = _configure_temporary_upload_root(
        monkeypatch,
        tmp_path,
    )

    destination = (
        product_dir
        / f"{store_id}-legacy.png"
    )

    resolved = (
        image_upload
        ._managed_path_from_url(
            (
                "http://10.12.168.137:8000"
                "/static/uploads/products/"
                + destination.name
            ),
            store_id,
        )
    )

    assert resolved == destination.resolve()


def test_external_managed_looking_url_is_not_owned(
    monkeypatch,
    tmp_path: Path,
):
    store_id = uuid4()

    _configure_temporary_upload_root(
        monkeypatch,
        tmp_path,
    )

    resolved = (
        image_upload
        ._managed_path_from_url(
            (
                "https://cdn.example.com"
                "/static/uploads/products/"
                f"{store_id}-external.png"
            ),
            store_id,
        )
    )

    assert resolved is None
