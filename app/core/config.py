from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    app_name: str = "FinPilot AI"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    async_database_url: Optional[str] = Field(default=None, alias="ASYNC_DATABASE_URL")

    jwt_secret_key: str = Field(default="change-me-access", alias="JWT_SECRET_KEY", min_length=16)
    jwt_refresh_secret_key: str = Field(default="change-me-refresh", alias="JWT_REFRESH_SECRET_KEY", min_length=16)
    algorithm: str = "HS256"

    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(default=60 * 24 * 7, alias="REFRESH_TOKEN_EXPIRE_MINUTES")

    default_admin_email: EmailStr = Field(default="admin@example.com", alias="DEFAULT_ADMIN_EMAIL")
    default_admin_password: str = Field(default="ChangeMe123!", alias="DEFAULT_ADMIN_PASSWORD")

    sqlite_path: Path = Path("./finpilot.db")

    @property
    def async_database_uri(self) -> str:
        """Return an async SQLAlchemy DSN with sensible fallbacks."""

        if self.async_database_url:
            return self.async_database_url

        if self.database_url:
            if self.database_url.startswith("postgresql+asyncpg://"):
                return self.database_url
            if self.database_url.startswith("postgresql://"):
                return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            if self.database_url.startswith("sqlite+aiosqlite://"):
                return self.database_url
            if self.database_url.startswith("sqlite://"):
                return self.database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

        return f"sqlite+aiosqlite:///{self.sqlite_path.resolve()}"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
