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

    # JWT Authentication
    jwt_expire_hours: int = 24
    jwt_algorithm: str = "HS256"

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

    # Distributor Credentials - LibDib
    libdib_email: Optional[str] = None
    libdib_password: Optional[str] = None
    libdib_entity_slug: Optional[str] = None
    libdib_session_id: Optional[str] = None
    libdib_csrf_token: Optional[str] = None

    # Distributor Credentials - Southern Glazer's (SGWS)
    sgws_email: Optional[str] = None
    sgws_password: Optional[str] = None
    sgws_account_id: Optional[str] = None

    # Distributor Credentials - RNDC (Republic National Distributing Company)
    rndc_email: Optional[str] = None
    rndc_password: Optional[str] = None
    rndc_account_id: Optional[str] = None

    # Distributor Credentials - SipMarket (Crest Beverage / Reyes)
    sipmarket_email: Optional[str] = None
    sipmarket_password: Optional[str] = None

    # Distributor Credentials - Park Street
    parkstreet_email: Optional[str] = None
    parkstreet_password: Optional[str] = None

    # Distributor Credentials - Breakthru Beverage
    breakthru_email: Optional[str] = None
    breakthru_password: Optional[str] = None

    # Distributor Credentials - Provi
    provi_email: Optional[str] = None
    provi_password: Optional[str] = None

    # Alerting & Notifications
    slack_webhook_url: Optional[str] = None
    alert_email_to: Optional[str] = None
    alert_email_from: Optional[str] = None
    sendgrid_api_key: Optional[str] = None

    # Circuit Breaker Settings
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 300  # seconds

    # Database SSL (for AWS RDS)
    db_ssl_required: bool = False

    # CORS - comma-separated list of allowed origins (NO wildcards in production)
    allowed_origins: str = "http://localhost:3000,https://abvtrends.vercel.app"

    # Production Scraper Settings
    # Items per run (catch-up: 100, maintenance: 50)
    scraper_items_per_run: int = 50
    scraper_catchup_items_per_run: int = 100
    # Hybrid scraping ratio (80% new, 20% refresh)
    scraper_new_items_ratio: float = 0.8
    scraper_refresh_items_ratio: float = 0.2
    # Time windows (hours in UTC)
    scraper_morning_window_start: int = 7  # 7 AM UTC
    scraper_morning_window_end: int = 11  # 11 AM UTC
    scraper_evening_window_start: int = 19  # 7 PM UTC
    scraper_evening_window_end: int = 23  # 11 PM UTC
    # Max jitter in minutes within window
    scraper_max_jitter_minutes: int = 60

    # Stealth Scraper Settings (human-like behavior)
    scraper_daily_limit_per_source: int = 150  # items/day per distributor
    scraper_batch_size: int = 20  # items per session
    scraper_min_delay_seconds: float = 3.0  # min delay between requests
    scraper_max_delay_seconds: float = 8.0  # max delay between requests
    scraper_sessions_per_day: int = 6  # scraping windows per day
    scraper_noise_ratio: float = 0.15  # 15% of actions are non-productive browsing
    scraper_business_hours_start: int = 8  # 8 AM PT
    scraper_business_hours_end: int = 18  # 6 PM PT
    scraper_skip_weekends: bool = True  # avoid scraping on weekends

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
