from fastapi import APIRouter
from app.api.v1 import auth, stores, products, public, orders, payments, sellers

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(stores.router)
api_router.include_router(products.router)
api_router.include_router(public.router)
api_router.include_router(orders.router)
api_router.include_router(payments.router)
api_router.include_router(sellers.router)
