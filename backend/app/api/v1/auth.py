from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.services.auth_rate_limit import clear_login_rate_limit, enforce_login_rate_limit
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    exists = await db.execute(select(User).where(User.email == payload.email.lower()))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=payload.email.lower(), full_name=payload.full_name, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=create_access_token(str(user.id), user.role))

@router.post("/login", response_model=TokenResponse)
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    await enforce_login_rate_limit(request, payload.email)
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(str(user.id), user.role))
