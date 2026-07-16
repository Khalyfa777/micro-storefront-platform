from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    FRONTEND_URL: str = "http://localhost:3000"
    DASHBOARD_PUBLIC_URL: str = "http://localhost:5173"
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"

    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me"

    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 30

    TRIAL_DAYS: int = 14

    PUBLIC_REGISTRATION_ENABLED: bool = False
    SELLER_INVITATION_EXPIRE_HOURS: int = 72
    SELLER_INVITATION_RATE_LIMIT_ATTEMPTS: int = 10
    SELLER_INVITATION_RATE_LIMIT_WINDOW_SECONDS: int = 300
    TRUST_PROXY_HEADERS: bool = False

    MAX_REQUEST_BODY_BYTES: int = 5 * 1024 * 1024
    IMAGE_UPLOAD_MAX_BYTES: int = 3 * 1024 * 1024
    IMAGE_UPLOAD_STORE_QUOTA_BYTES: int = 512 * 1024 * 1024
    IMAGE_UPLOAD_ORPHAN_TTL_SECONDS: int = 24 * 60 * 60
    IMAGE_UPLOAD_RATE_LIMIT_ATTEMPTS: int = 20
    IMAGE_UPLOAD_RATE_LIMIT_WINDOW_SECONDS: int = 300

    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_settings(self):
        if self.SELLER_INVITATION_EXPIRE_HOURS <= 0:
            raise ValueError(
                "SELLER_INVITATION_EXPIRE_HOURS must be greater than zero."
            )

        if self.SELLER_INVITATION_RATE_LIMIT_ATTEMPTS <= 0:
            raise ValueError(
                "SELLER_INVITATION_RATE_LIMIT_ATTEMPTS must be greater than zero."
            )

        if self.SELLER_INVITATION_RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise ValueError(
                "SELLER_INVITATION_RATE_LIMIT_WINDOW_SECONDS must be greater than zero."
            )

        positive_image_settings = {
            "MAX_REQUEST_BODY_BYTES": self.MAX_REQUEST_BODY_BYTES,
            "IMAGE_UPLOAD_MAX_BYTES": self.IMAGE_UPLOAD_MAX_BYTES,
            "IMAGE_UPLOAD_STORE_QUOTA_BYTES": (
                self.IMAGE_UPLOAD_STORE_QUOTA_BYTES
            ),
            "IMAGE_UPLOAD_ORPHAN_TTL_SECONDS": (
                self.IMAGE_UPLOAD_ORPHAN_TTL_SECONDS
            ),
            "IMAGE_UPLOAD_RATE_LIMIT_ATTEMPTS": (
                self.IMAGE_UPLOAD_RATE_LIMIT_ATTEMPTS
            ),
            "IMAGE_UPLOAD_RATE_LIMIT_WINDOW_SECONDS": (
                self.IMAGE_UPLOAD_RATE_LIMIT_WINDOW_SECONDS
            ),
        }

        for name, value in positive_image_settings.items():
            if value <= 0:
                raise ValueError(
                    f"{name} must be greater than zero."
                )

        if self.IMAGE_UPLOAD_STORE_QUOTA_BYTES < self.IMAGE_UPLOAD_MAX_BYTES:
            raise ValueError(
                "IMAGE_UPLOAD_STORE_QUOTA_BYTES must be at least "
                "IMAGE_UPLOAD_MAX_BYTES."
            )

        if self.MAX_REQUEST_BODY_BYTES <= self.IMAGE_UPLOAD_MAX_BYTES:
            raise ValueError(
                "MAX_REQUEST_BODY_BYTES must be greater than "
                "IMAGE_UPLOAD_MAX_BYTES to allow multipart overhead."
            )

        environment = self.ENVIRONMENT.strip().lower()
        local_environments = {
            "development",
            "dev",
            "local",
            "test",
            "testing",
        }

        if environment in local_environments:
            return self

        weak_secret_keys = {
            "change-me",
            "dev-secret-change-later",
            "dev-local-secret-change-before-production",
            "replace-with-a-long-random-64-character-secret",
        }

        if self.SECRET_KEY in weak_secret_keys or len(self.SECRET_KEY) < 32:
            raise ValueError(
                "Production SECRET_KEY must be a strong random value "
                "of at least 32 characters."
            )

        local_markers = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        ]

        url_values = {
            "FRONTEND_URL": self.FRONTEND_URL,
            "DASHBOARD_PUBLIC_URL": self.DASHBOARD_PUBLIC_URL,
            "BACKEND_PUBLIC_URL": self.BACKEND_PUBLIC_URL,
            "CORS_ORIGINS": self.CORS_ORIGINS,
            "DATABASE_URL": self.DATABASE_URL,
        }

        for name, value in url_values.items():
            if any(marker in value for marker in local_markers):
                raise ValueError(
                    f"Deployed {name} cannot contain localhost "
                    "or local IP addresses."
                )

        public_urls = {
            "FRONTEND_URL": self.FRONTEND_URL,
            "DASHBOARD_PUBLIC_URL": self.DASHBOARD_PUBLIC_URL,
            "BACKEND_PUBLIC_URL": self.BACKEND_PUBLIC_URL,
        }

        for name, value in public_urls.items():
            if not value.lower().startswith("https://"):
                raise ValueError(
                    f"Deployed {name} must use an HTTPS URL."
                )

        if (
            "postgres:postgres" in self.DATABASE_URL
            or "CHANGE_ME" in self.DATABASE_URL
        ):
            raise ValueError(
                "Production DATABASE_URL contains unsafe default "
                "or placeholder credentials."
            )

        if (
            not self.PAYSTACK_SECRET_KEY
            or not self.PAYSTACK_SECRET_KEY.startswith("sk_live_")
        ):
            raise ValueError(
                "Production PAYSTACK_SECRET_KEY must be configured "
                "with a live Paystack secret key."
            )

        if (
            not self.PAYSTACK_PUBLIC_KEY
            or not self.PAYSTACK_PUBLIC_KEY.startswith("pk_live_")
        ):
            raise ValueError(
                "Production PAYSTACK_PUBLIC_KEY must be configured "
                "with a live Paystack public key."
            )

        return self

    @property
    def cors_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
