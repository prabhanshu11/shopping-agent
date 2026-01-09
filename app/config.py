"""Application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Shopping Agent"
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./shopping_agent.db"

    # Security
    secret_key: str = "change-me-in-production"

    # API Keys (loaded from pass or .env)
    amazon_api_key: str | None = None
    swiggy_api_key: str | None = None
    blinkit_api_key: str | None = None
    ubereats_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
