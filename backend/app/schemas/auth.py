from pydantic import (
    BaseModel,
    EmailStr,
    Field,
)


class RegisterRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=255,
    )
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        min_length=1,
        max_length=128,
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
    )


class ChangePasswordResponse(BaseModel):
    detail: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
