from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine
from app.middleware.request_body_limit import (
    RequestBodyLimitMiddleware,
)
from app.services.image_upload import (
    ensure_upload_directories,
)


ensure_upload_directories()

app = FastAPI(
    title="Micro Storefront Platform API",
    version="0.1.0",
)

app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_bytes=(
        settings.MAX_REQUEST_BODY_BYTES
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text("SELECT 1")
            )

        return {
            "status": "ok",
            "database": "ok",
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "database": "unavailable",
            },
        )


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)
