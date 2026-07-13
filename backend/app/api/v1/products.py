from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_store_owner
from app.db.session import get_db
from app.models import Store, Product
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.plan_limits import get_product_limit_for_store, get_product_limit_message
from app.services.plan_features import ensure_plan_allows_image_uploads


router = APIRouter(tags=["products"])

async def lock_store_for_product_limit(db: AsyncSession, store: Store) -> Store:
    result = await db.execute(
        select(Store)
        .where(Store.id == store.id)
        .with_for_update()
    )

    locked_store = result.scalar_one_or_none()

    if not locked_store:
        raise HTTPException(status_code=404, detail="Store not found")

    return locked_store


async def ensure_published_store_keeps_active_product(
    db: AsyncSession,
    store: Store,
) -> None:
    publication_status = (
        store.publication_status
        or "draft"
    ).lower().strip()

    if publication_status != "published":
        return

    active_count_result = await db.execute(
        select(
            func.count(Product.id)
        ).where(
            Product.store_id == store.id,
            Product.is_active.is_(True),
        )
    )

    active_product_count = (
        active_count_result.scalar_one()
    )

    if active_product_count <= 1:
        raise HTTPException(
            status_code=409,
            detail=(
                "A published store must keep at "
                "least one active product. "
                "Unpublish the store before "
                "deactivating its last active "
                "product."
            ),
        )


@router.get("/stores/{store_id}/products", response_model=list[ProductResponse])
async def list_products(
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product)
        .where(Product.store_id == store.id)
        .order_by(Product.created_at.desc())
    )

    return result.scalars().all()


@router.post("/stores/{store_id}/products", response_model=ProductResponse)
async def create_product(
    payload: ProductCreate,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    existing_result = await db.execute(
        select(Product).where(
            Product.store_id == store.id,
            Product.slug == payload.slug,
        )
    )
    existing_product = existing_result.scalar_one_or_none()

    if existing_product:
        raise HTTPException(
            status_code=400,
            detail="A product with this slug already exists in this store",
        )

    if payload.is_active:
        store = await lock_store_for_product_limit(db, store)
        plan_limit = await get_product_limit_for_store(db, store)

        if plan_limit is not None:
            active_count_result = await db.execute(
                select(func.count(Product.id)).where(
                    Product.store_id == store.id,
                    Product.is_active.is_(True),
                )
            )

            active_product_count = active_count_result.scalar_one()

            if active_product_count >= plan_limit:
                raise HTTPException(
                    status_code=403,
                    detail=get_product_limit_message(store.plan_name, plan_limit),
                )

    product = Product(
        store_id=store.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        image_url=payload.image_url,
        product_type=payload.product_type,
        price=payload.price,
        stock_quantity=payload.stock_quantity,
        is_active=payload.is_active,
        is_featured=payload.is_featured,
    )

    db.add(product)
    await db.commit()
    await db.refresh(product)

    return product


@router.patch("/stores/{store_id}/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    update_data = payload.model_dump(
        exclude_unset=True
    )

    changes_active_state = (
        "is_active" in update_data
    )

    if changes_active_state:
        store = (
            await lock_store_for_product_limit(
                db,
                store,
            )
        )

    product_query = select(Product).where(
        Product.id == product_id,
        Product.store_id == store.id,
    )

    if changes_active_state:
        product_query = (
            product_query.with_for_update()
        )

    result = await db.execute(
        product_query
    )

    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    if "slug" in update_data:
        existing_result = await db.execute(
            select(Product).where(
                Product.store_id == store.id,
                Product.slug == update_data["slug"],
                Product.id != product.id,
            )
        )
        existing_product = existing_result.scalar_one_or_none()

        if existing_product:
            raise HTTPException(
                status_code=400,
                detail="Another product with this slug already exists",
            )

    is_being_activated = (
        update_data.get("is_active") is True
        and not product.is_active
    )

    is_being_deactivated = (
        update_data.get("is_active") is False
        and product.is_active
    )

    if is_being_activated:
        plan_limit = await get_product_limit_for_store(db, store)

        if plan_limit is not None:
            active_count_result = await db.execute(
                select(func.count(Product.id)).where(
                    Product.store_id == store.id,
                    Product.is_active.is_(True),
                )
            )

            active_product_count = active_count_result.scalar_one()

            if active_product_count >= plan_limit:
                raise HTTPException(
                    status_code=403,
                    detail=get_product_limit_message(
                        store.plan_name,
                        plan_limit,
                    ),
                )

    if is_being_deactivated:
        await (
            ensure_published_store_keeps_active_product(
                db,
                store,
            )
        )

    for key, value in update_data.items():
        setattr(product, key, value)

    await db.commit()
    await db.refresh(product)

    return product


@router.delete("/stores/{store_id}/products/{product_id}")
async def delete_product(
    product_id: UUID,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    store = await lock_store_for_product_limit(
        db,
        store,
    )

    result = await db.execute(
        select(Product)
        .where(
            Product.id == product_id,
            Product.store_id == store.id,
        )
        .with_for_update()
    )

    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    if product.is_active:
        await (
            ensure_published_store_keeps_active_product(
                db,
                store,
            )
        )

    product.is_active = False

    await db.commit()

    return {
        "status": "success",
        "message": "Product deactivated successfully",
    }




# ============================
# PRODUCT IMAGE UPLOAD
# ============================

import base64
import binascii
import io
import os
from uuid import uuid4

from PIL import Image
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.image_validation import validate_uploaded_image_safety


class ProductImageUploadPayload(BaseModel):
    filename: str
    content_type: str
    data_base64: str = Field(min_length=1)


@router.post("/stores/{store_id}/uploads/product-image")
async def upload_product_image(
    payload: ProductImageUploadPayload,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    await ensure_plan_allows_image_uploads(db, store)

    allowed_types = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    if payload.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, PNG, and WEBP images are allowed.",
        )

    try:
        image_bytes = base64.b64decode(payload.data_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="Invalid image data.")

    max_size_bytes = 3 * 1024 * 1024

    if len(image_bytes) > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail="Image is too large. Maximum size is 3MB.",
        )


    validate_uploaded_image_safety(image_bytes)
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is not a valid image.",
        )

    upload_dir = "static/uploads/products"
    os.makedirs(upload_dir, exist_ok=True)

    extension = allowed_types[payload.content_type]
    safe_filename = f"{store.id}-{uuid4().hex}{extension}"
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as file:
        file.write(image_bytes)

    image_url = f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/{file_path.replace(os.sep, '/')}"

    return {
        "image_url": image_url,
    }
