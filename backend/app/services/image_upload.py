import asyncio
import logging
import os
import time
from ipaddress import ip_address
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Product, Store
from app.services.image_validation import (
    validate_uploaded_image_safety,
)


logger = logging.getLogger(__name__)

ImageCategory = Literal[
    "product",
    "logo",
    "banner",
]

_PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

UPLOAD_ROOT = (
    _PROJECT_ROOT
    / "static"
    / "uploads"
)

_UPLOAD_DIRECTORIES = {
    "product": (
        UPLOAD_ROOT
        / "products"
    ),
    "logo": (
        UPLOAD_ROOT
        / "stores"
        / "logos"
    ),
    "banner": (
        UPLOAD_ROOT
        / "stores"
        / "banners"
    ),
}

_ALLOWED_DECLARED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

_READ_CHUNK_BYTES = 64 * 1024


def ensure_upload_directories() -> None:
    for directory in (
        _UPLOAD_DIRECTORIES.values()
    ):
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


async def read_and_validate_image_upload(
    upload: UploadFile,
) -> tuple[bytes, str]:
    declared_content_type = (
        upload.content_type or ""
    ).strip().lower()

    if (
        declared_content_type
        not in _ALLOWED_DECLARED_CONTENT_TYPES
    ):
        await upload.close()

        raise HTTPException(
            status_code=400,
            detail=(
                "Only JPG, PNG, and WEBP "
                "images are allowed."
            ),
        )

    image_data = bytearray()

    try:
        while True:
            chunk = await upload.read(
                _READ_CHUNK_BYTES
            )

            if not chunk:
                break

            image_data.extend(chunk)

            if (
                len(image_data)
                > settings.IMAGE_UPLOAD_MAX_BYTES
            ):
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "Image is too large. "
                        "Maximum size is 3MB."
                    ),
                )
    finally:
        await upload.close()

    image_bytes = bytes(image_data)

    extension = await asyncio.to_thread(
        validate_uploaded_image_safety,
        image_bytes,
        declared_content_type,
    )

    return image_bytes, extension


def _file_prefix(
    store_id: UUID,
    category: ImageCategory,
) -> str:
    if category == "product":
        return f"{store_id}-"

    return f"{store_id}-{category}-"


def _iter_store_files(
    store_id: UUID,
):
    store_id_text = str(store_id)

    for category, directory in (
        _UPLOAD_DIRECTORIES.items()
    ):
        if not directory.exists():
            continue

        prefix = _file_prefix(
            store_id,
            category,
        )

        for path in directory.glob(
            f"{prefix}*"
        ):
            if path.is_file():
                yield path


def _is_local_or_private_hostname(
    hostname: str | None,
) -> bool:
    if not hostname:
        return False

    normalized = (
        hostname
        .strip()
        .lower()
        .strip("[]")
    )

    if (
        normalized in {
            "localhost",
            "0.0.0.0",
            "::1",
        }
        or normalized.endswith(".local")
    ):
        return True

    try:
        address = ip_address(normalized)
    except ValueError:
        return False

    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_unspecified
    )


def _managed_path_from_url(
    image_url: str | None,
    store_id: UUID,
) -> Path | None:
    value = str(
        image_url or ""
    ).strip()

    if not value:
        return None

    try:
        parsed_url = urlparse(value)
        backend_url = urlparse(
            settings.BACKEND_PUBLIC_URL
        )
    except ValueError:
        return None

    if (
        parsed_url.query
        or parsed_url.fragment
    ):
        return None

    is_relative_reference = (
        not parsed_url.scheme
        and not parsed_url.netloc
    )

    if not is_relative_reference:
        is_current_backend = (
            parsed_url.scheme
            == backend_url.scheme
            and parsed_url.netloc
            == backend_url.netloc
        )

        if (
            not is_current_backend
            and not _is_local_or_private_hostname(
                parsed_url.hostname
            )
        ):
            return None

    decoded_path = unquote(
        parsed_url.path
    )

    upload_prefix = (
        "/static/uploads/"
    )

    if not decoded_path.startswith(
        upload_prefix
    ):
        return None

    relative_path = decoded_path.lstrip(
        "/"
    )

    candidate = (
        _PROJECT_ROOT
        / relative_path
    ).resolve()

    upload_root = UPLOAD_ROOT.resolve()

    if not candidate.is_relative_to(
        upload_root
    ):
        return None

    if not candidate.name.startswith(
        f"{store_id}-"
    ):
        return None

    return candidate


def _collect_referenced_paths(
    referenced_urls: set[str],
    store_id: UUID,
) -> set[Path]:
    referenced_paths: set[Path] = set()

    for image_url in referenced_urls:
        managed_path = (
            _managed_path_from_url(
                image_url,
                store_id,
            )
        )

        if managed_path is not None:
            referenced_paths.add(
                managed_path
            )

    return referenced_paths


def _cleanup_orphaned_files_sync(
    store_id: UUID,
    referenced_urls: set[str],
) -> None:
    referenced_paths = (
        _collect_referenced_paths(
            referenced_urls,
            store_id,
        )
    )

    cutoff = (
        time.time()
        - settings
        .IMAGE_UPLOAD_ORPHAN_TTL_SECONDS
    )

    for path in list(
        _iter_store_files(store_id)
    ):
        try:
            if (
                path.resolve()
                in referenced_paths
            ):
                continue

            if path.stat().st_mtime > cutoff:
                continue

            path.unlink(
                missing_ok=True
            )
        except OSError:
            logger.warning(
                "Could not remove orphaned "
                "image upload. path=%s",
                path,
                exc_info=True,
            )


def _store_storage_bytes_sync(
    store_id: UUID,
) -> int:
    total = 0

    for path in _iter_store_files(
        store_id
    ):
        try:
            total += path.stat().st_size
        except OSError:
            logger.warning(
                "Could not inspect image "
                "upload size. path=%s",
                path,
                exc_info=True,
            )

    return total


def _atomic_write_sync(
    destination: Path,
    image_bytes: bytes,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        destination.parent
        / (
            f".{destination.name}."
            f"{uuid4().hex}.tmp"
        )
    )

    try:
        with temporary_path.open(
            "xb"
        ) as output_file:
            output_file.write(
                image_bytes
            )
            output_file.flush()
            os.fsync(
                output_file.fileno()
            )

        os.replace(
            temporary_path,
            destination,
        )
    finally:
        temporary_path.unlink(
            missing_ok=True
        )


def _public_url_for_path(
    path: Path,
) -> str:
    relative_path = path.resolve().relative_to(
        _PROJECT_ROOT
    )

    relative_url = "/".join(
        relative_path.parts
    )

    return "/" + relative_url


async def get_referenced_image_urls(
    db: AsyncSession,
    store_id: UUID,
) -> set[str]:
    references: set[str] = set()

    store_result = await db.execute(
        select(
            Store.logo_url,
            Store.banner_url,
        ).where(
            Store.id == store_id
        )
    )

    store_row = (
        store_result.one_or_none()
    )

    if store_row is not None:
        for value in store_row:
            if value:
                references.add(
                    value
                )

    product_result = await db.execute(
        select(
            Product.image_url
        ).where(
            Product.store_id == store_id,
            Product.image_url.is_not(
                None
            ),
        )
    )

    for value in (
        product_result.scalars().all()
    ):
        if value:
            references.add(value)

    return references


async def persist_uploaded_image(
    *,
    upload: UploadFile,
    store_id: UUID,
    category: ImageCategory,
    referenced_urls: set[str],
) -> str:
    if category not in _UPLOAD_DIRECTORIES:
        await upload.close()

        raise HTTPException(
            status_code=400,
            detail="Invalid image category.",
        )

    image_bytes, extension = (
        await read_and_validate_image_upload(
            upload
        )
    )

    await asyncio.to_thread(
        _cleanup_orphaned_files_sync,
        store_id,
        referenced_urls,
    )

    current_storage_bytes = (
        await asyncio.to_thread(
            _store_storage_bytes_sync,
            store_id,
        )
    )

    if (
        current_storage_bytes
        + len(image_bytes)
        > settings
        .IMAGE_UPLOAD_STORE_QUOTA_BYTES
    ):
        raise HTTPException(
            status_code=507,
            detail=(
                "Store image storage quota "
                "has been reached."
            ),
        )

    directory = (
        _UPLOAD_DIRECTORIES[category]
    )

    filename = (
        _file_prefix(
            store_id,
            category,
        )
        + uuid4().hex
        + extension
    )

    destination = (
        directory
        / filename
    )

    await asyncio.to_thread(
        _atomic_write_sync,
        destination,
        image_bytes,
    )

    final_storage_bytes = (
        await asyncio.to_thread(
            _store_storage_bytes_sync,
            store_id,
        )
    )

    if (
        final_storage_bytes
        > settings
        .IMAGE_UPLOAD_STORE_QUOTA_BYTES
    ):
        await asyncio.to_thread(
            destination.unlink,
            True,
        )

        raise HTTPException(
            status_code=507,
            detail=(
                "Store image storage quota "
                "has been reached."
            ),
        )

    return _public_url_for_path(
        destination
    )


async def delete_managed_image_if_unreferenced(
    *,
    db: AsyncSession,
    store_id: UUID,
    image_url: str | None,
) -> None:
    managed_path = (
        _managed_path_from_url(
            image_url,
            store_id,
        )
    )

    if managed_path is None:
        return

    try:
        referenced_urls = (
            await get_referenced_image_urls(
                db,
                store_id,
            )
        )

        if image_url in referenced_urls:
            return

        await asyncio.to_thread(
            managed_path.unlink,
            True,
        )
    except Exception:
        logger.warning(
            "Could not remove replaced "
            "managed image. store_id=%s "
            "image_url=%s",
            store_id,
            image_url,
            exc_info=True,
        )
