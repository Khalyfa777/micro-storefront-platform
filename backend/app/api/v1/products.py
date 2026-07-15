from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_store_owner
from app.db.session import get_db
from app.models import Store, Product
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.image_upload import (
    delete_managed_image_if_unreferenced,
    get_referenced_image_urls,
    persist_uploaded_image,
)
from app.services.image_upload_rate_limit import (
    enforce_image_upload_rate_limit,
)
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

    previous_image_url = (
        product.image_url
        if "image_url" in update_data
        else None
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

    if (
        previous_image_url
        and previous_image_url
        != product.image_url
    ):
        await (
            delete_managed_image_if_unreferenced(
                db=db,
                store_id=store.id,
                image_url=previous_image_url,
            )
        )

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


@router.post(
    "/stores/{store_id}/uploads/product-image"
)
async def upload_product_image(
    file: UploadFile = File(...),
    store: Store = Depends(
        require_store_owner
    ),
    db: AsyncSession = Depends(get_db),
):
    await ensure_plan_allows_image_uploads(
        db,
        store,
    )

    await enforce_image_upload_rate_limit(
        store.id
    )

    referenced_urls = (
        await get_referenced_image_urls(
            db,
            store.id,
        )
    )

    image_url = await persist_uploaded_image(
        upload=file,
        store_id=store.id,
        category="product",
        referenced_urls=referenced_urls,
    )

    return {
        "image_url": image_url,
    }
