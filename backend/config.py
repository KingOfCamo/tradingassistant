import os

from pydantic_settings import BaseSettings
from typing import Optional


def _fix_database_url(url: str) -> str:
    """Convert Railway's DATABASE_URL to asyncpg format."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


class Settings(BaseSettings):
    # AI
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # Market Data — primary feeds
    # Twelve Data: ASX quotes/OHLCV/indicators/earnings (free tier 800 credits/day)
    twelve_data_api_key: str = ""
    twelve_data_daily_credit_limit: int = 800
    twelve_data_credits_warning_pct: int = 80
    # Free tier: 8 credits/minute. Pro: 500. Raise via env when upgraded.
    twelve_data_per_minute_limit: int = 8
    # Max symbols per scan — helps on free tiers where per-minute limits
    # make scanning 200 symbols impractical. Raise when you upgrade.
    scan_max_symbols: int = 5
    # Plan tier controls whether Twelve Data is used for ASX symbols.
    # Free tier = US-only (ASX falls back to yfinance).
    # "pro" / "venture" / "enterprise" = ASX included, Twelve Data becomes
    # the primary ASX source. Flip this env var when you upgrade.
    twelve_data_plan_tier: str = "free"

    # FRED: macro series (VIX history, yield curve, Fed/RBA rates, CPI) — always free
    fred_api_key: str = ""
    fred_cache_ttl_seconds: int = 86400  # 24h — macro data changes daily at most

    # Finnhub: US quotes/news/VIX/insider (optional — free tier)
    finnhub_api_key: str = ""

    # Cache TTLs (Redis)
    quote_cache_ttl_seconds: int = 900              # 15m — matches scan interval
    ohlcv_daily_cache_ttl_seconds: int = 86400      # 24h for completed daily bars
    ohlcv_intraday_cache_ttl_seconds: int = 900     # 15m

    # Database — Railway sets DATABASE_URL and REDIS_URL automatically
    database_url: str = "postgresql+asyncpg://trader:password@localhost:5432/tradingassistant"
    redis_url: str = "redis://localhost:6379"

    # Railway
    port: int = 8000  # Railway sets PORT env var
    railway_public_domain: str = ""  # e.g. your-app.up.railway.app

    # Notifications (optional)
    alert_email: Optional[str] = None

    # User Profile
    user_name: str = "Trader"
    default_currency: str = "AUD"
    home_market: str = "ASX"
    portfolio_value_aud: float = 5000.0
    risk_per_trade_pct: float = 1.5
    max_position_size_pct: float = 10.0

    # Core ETF Holdings
    core_holdings: str = "VAS.AX:0:0.00,IHVV.AX:0:0.00"

    # Portfolio Risk Limits
    max_sector_concentration_pct: float = 35.0
    max_portfolio_beta: float = 1.5
    correlation_warning_threshold: float = 0.75

    # Broker: CMC Markets
    cmc_au_threshold: float = 1000.00
    cmc_au_flat_fee: float = 9.90
    cmc_fx_spread_pct: float = 0.0065

    # Market Regime
    regime_vix_elevated: float = 20.0
    regime_vix_extreme: float = 30.0
    regime_adx_trending: float = 25.0
    regime_breadth_bullish: float = 0.60

    # Confluence Engine
    confluence_min_strategies: int = 2
    confluence_priority_threshold: int = 3

    # Scanning
    scan_universe: str = "ASX200,SP500"
    scan_interval_minutes: int = 15
    ai_analysis_daily_limit: int = 50

    # Idea Lifecycle
    idea_max_age_days: int = 5
    idea_entry_miss_pct: float = 3.0

    # Cloudflare
    cloudflare_tunnel_token: str = ""
    cloudflare_domain: str = ""

    # App
    api_port: int = 8000
    frontend_port: int = 3000
    secret_key: str = "replace_this_with_a_long_random_string_at_least_32_chars"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    def warn_if_feeds_missing(self) -> list[str]:
        """Return a list of missing required feed keys. Logged at startup by app.py."""
        missing = []
        if not self.twelve_data_api_key:
            missing.append("TWELVE_DATA_API_KEY")
        if not self.fred_api_key:
            missing.append("FRED_API_KEY")
        return missing

    def get_async_database_url(self) -> str:
        return _fix_database_url(self.database_url)

    def get_sync_database_url(self) -> str:
        url = self.database_url
        # Strip async driver for sync operations (alembic, etc.)
        for prefix in ("postgres://", "postgresql://", "postgresql+asyncpg://"):
            if url.startswith(prefix):
                return "postgresql://" + url[len(prefix):]
        return url


settings = Settings()
# Fix DB URL in-place for modules that read it directly
settings.database_url = _fix_database_url(settings.database_url)
