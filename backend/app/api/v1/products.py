from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy import delete, select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_store_owner
from app.db.session import get_db

from app.models import (
    Product,
    ProductOrderField,
    ProductOrderFieldOption,
    Store,
)

from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.schemas.product_order_field import (
    ProductOrderFieldResponse,
    ProductOrderFieldsReplace,
)
from app.services.conversational_ordering import (
    normalize_fulfillment_configuration,
    validate_order_field_definitions,
)
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



async def _replace_product_order_fields_in_transaction(
    db: AsyncSession,
    product_id: UUID,
    definitions: list[dict],
) -> None:
    await db.execute(
        delete(ProductOrderField).where(
            ProductOrderField.product_id == product_id
        )
    )
    await db.flush()

    for definition in definitions:
        field_data = dict(definition)
        options = list(field_data.pop("options", []))
        order_field = ProductOrderField(
            product_id=product_id,
            **field_data,
        )
        db.add(order_field)
        await db.flush()

        for option in options:
            db.add(
                ProductOrderFieldOption(
                    field_id=order_field.id,
                    **option,
                )
            )

    await db.flush()


@router.get("/stores/{store_id}/products", response_model=list[ProductResponse])
async def list_products(
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.order_fields).selectinload(
                ProductOrderField.options
            )
        )
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

    order_field_definitions = validate_order_field_definitions(
        field.model_dump() for field in payload.order_fields
    )

    product = Product(
        store_id=store.id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        image_url=payload.image_url,
        product_type=payload.product_type,
        default_fulfillment_method=payload.default_fulfillment_method,
        allowed_fulfillment_methods=payload.allowed_fulfillment_methods,
        price=payload.price,
        stock_quantity=payload.stock_quantity,
        is_active=payload.is_active,
        is_featured=payload.is_featured,
    )

    try:
        db.add(product)
        await db.flush()
        await _replace_product_order_fields_in_transaction(
            db,
            product.id,
            order_field_definitions,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return await _get_owned_product_with_order_fields(
        product.id,
        store,
        db,
    )


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
    order_fields_were_supplied = (
        "order_fields" in update_data
    )
    order_fields_payload = update_data.pop(
        "order_fields",
        None,
    )
    order_field_definitions = None

    if order_fields_were_supplied:
        order_field_definitions = (
            validate_order_field_definitions(
                order_fields_payload or []
            )
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

    if (
        changes_active_state
        or order_fields_were_supplied
    ):
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

    fulfillment_keys = {
        "product_type",
        "default_fulfillment_method",
        "allowed_fulfillment_methods",
    }
    if fulfillment_keys.intersection(update_data):
        merged_product_type = update_data.get(
            "product_type", product.product_type
        )
        merged_default = update_data.get(
            "default_fulfillment_method",
            product.default_fulfillment_method,
        )
        merged_allowed = update_data.get(
            "allowed_fulfillment_methods",
            product.allowed_fulfillment_methods,
        )
        try:
            normalized_default, normalized_allowed = (
                normalize_fulfillment_configuration(
                    merged_product_type,
                    merged_default,
                    merged_allowed,
                )
            )
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error
        update_data["default_fulfillment_method"] = normalized_default
        update_data["allowed_fulfillment_methods"] = normalized_allowed

    try:
        for key, value in update_data.items():
            setattr(product, key, value)

        if (
            order_fields_were_supplied
            and order_field_definitions is not None
        ):
            await _replace_product_order_fields_in_transaction(
                db,
                product.id,
                order_field_definitions,
            )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    configured_product = (
        await _get_owned_product_with_order_fields(
            product.id,
            store,
            db,
        )
    )

    if (
        previous_image_url
        and previous_image_url
        != configured_product.image_url
    ):
        await (
            delete_managed_image_if_unreferenced(
                db=db,
                store_id=store.id,
                image_url=previous_image_url,
            )
        )

    return configured_product


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


async def _get_owned_product_with_order_fields(
    product_id: UUID,
    store: Store,
    db: AsyncSession,
    *,
    lock: bool = False,
) -> Product:
    query = (
        select(Product)
        .options(
            selectinload(Product.order_fields).selectinload(
                ProductOrderField.options
            )
        )
        .where(
            Product.id == product_id,
            Product.store_id == store.id,
        )
    )
    if lock:
        query = query.with_for_update()
    query = query.execution_options(populate_existing=True)
    result = await db.execute(query)
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get(
    "/stores/{store_id}/products/{product_id}/order-fields",
    response_model=list[ProductOrderFieldResponse],
)
async def list_product_order_fields(
    product_id: UUID,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    product = await _get_owned_product_with_order_fields(
        product_id,
        store,
        db,
    )
    return product.order_fields


@router.put(
    "/stores/{store_id}/products/{product_id}/order-fields",
    response_model=list[ProductOrderFieldResponse],
)
async def replace_product_order_fields(
    product_id: UUID,
    payload: ProductOrderFieldsReplace,
    store: Store = Depends(require_store_owner),
    db: AsyncSession = Depends(get_db),
):
    product = await _get_owned_product_with_order_fields(
        product_id,
        store,
        db,
        lock=True,
    )
    try:
        definitions = validate_order_field_definitions(
            field.model_dump() for field in payload.fields
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    try:
        await _replace_product_order_fields_in_transaction(
            db,
            product.id,
            definitions,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    configured_product = await _get_owned_product_with_order_fields(
        product_id,
        store,
        db,
    )
    return configured_product.order_fields


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
