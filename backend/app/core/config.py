"""
ABVTrends - Application Configuration

Centralized configuration management using Pydantic Settings.
All environment variables are loaded and validated here.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "ABVTrends"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/abvtrends"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    secret_key: str = "change-me-in-production-use-secrets-generate"
    api_key_header: str = "X-API-Key"

    # Rate Limiting
    rate_limit_per_minute: int = 100

    # Scraper Settings
    scraper_delay_seconds: float = 2.0
    max_concurrent_scrapers: int = 3
    scraper_timeout_seconds: int = 30
    scraper_max_retries: int = 3
    user_agent: str = (
        "ABVTrends/1.0 (https://abvtrends.com; contact@abvtrends.com) "
        "Python/3.11 Research Bot"
    )

    # ML Settings
    forecast_horizon_days: int = 7
    model_retrain_hour: int = 3  # 3 AM UTC
    min_data_points_for_training: int = 30
    model_storage_path: str = "./models"

    # Trend Score Weights
    weight_media_mentions: float = 0.20
    weight_social_velocity: float = 0.20
    weight_retailer_presence: float = 0.15
    weight_price_movement: float = 0.15
    weight_search_interest: float = 0.15
    weight_seasonal_alignment: float = 0.15

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # External APIs
    google_trends_api_key: Optional[str] = None
    social_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # CORS
    allowed_origins: str = "http://localhost:3000"

    @property
    def async_database_url(self) -> str:
        """Convert sync database URL to async format for SQLAlchemy async engine."""
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return self.database_url

    @property
    def sync_database_url(self) -> str:
        """Ensure sync database URL format for Alembic migrations."""
        if "asyncpg" in self.database_url:
            return self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        return self.database_url


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


# Convenience export
settings = get_settings()
