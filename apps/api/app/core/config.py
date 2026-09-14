"""Application configuration, loaded from environment / .env."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Sailbase API"
    environment: str = Field(default="development")  # development | test | production
    database_url: str = Field(default="sqlite:///./sailbase.db")
    secret_key: str = Field(default="dev-secret-change-me-before-going-live-0123456789")
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:3000"
    public_web_url: str = "http://localhost:3000"

    # Payments
    payment_provider: str = "fake"  # fake | stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    deposit_percent: int = 30
    currency: str = "EUR"

    # Booking lifecycle
    quote_ttl_minutes: int = 30
    hold_ttl_minutes: int = 45

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
