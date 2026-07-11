from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    TRIAL_DAYS: int = 14
    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379/0"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    PAYSTACK_SECRET_KEY: str = ""
    PAYSTACK_PUBLIC_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.ENVIRONMENT.lower() != "production":
            return self

        weak_secret_keys = {
            "change-me",
            "dev-secret-change-later",
            "dev-local-secret-change-before-production",
            "replace-with-a-long-random-64-character-secret",
        }

        if self.SECRET_KEY in weak_secret_keys or len(self.SECRET_KEY) < 32:
            raise ValueError("Production SECRET_KEY must be a strong random value of at least 32 characters.")

        local_markers = ["localhost", "127.0.0.1", "0.0.0.0"]

        url_values = {
            "FRONTEND_URL": self.FRONTEND_URL,
            "BACKEND_PUBLIC_URL": self.BACKEND_PUBLIC_URL,
            "CORS_ORIGINS": self.CORS_ORIGINS,
            "DATABASE_URL": self.DATABASE_URL,
        }

        for name, value in url_values.items():
            if any(marker in value for marker in local_markers):
                raise ValueError(f"Production {name} cannot contain localhost or local IP addresses.")

        if "postgres:postgres" in self.DATABASE_URL or "CHANGE_ME" in self.DATABASE_URL:
            raise ValueError("Production DATABASE_URL contains unsafe default or placeholder credentials.")

        if not self.PAYSTACK_SECRET_KEY or not self.PAYSTACK_SECRET_KEY.startswith("sk_live_"):
            raise ValueError("Production PAYSTACK_SECRET_KEY must be configured with a live Paystack secret key.")

        if not self.PAYSTACK_PUBLIC_KEY or not self.PAYSTACK_PUBLIC_KEY.startswith("pk_live_"):
            raise ValueError("Production PAYSTACK_PUBLIC_KEY must be configured with a live Paystack public key.")

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