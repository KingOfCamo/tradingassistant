"""S&P 500 universe manager."""

import logging
from dataclasses import dataclass

from backend.data.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

UNIVERSE_CACHE_TTL = 604800  # 7 days


@dataclass
class SP500Stock:
    symbol: str
    company_name: str
    gics_sector: str
    market_cap_usd: float


# Representative sample of S&P 500 constituents
SP500_CORE = [
    SP500Stock("AAPL", "Apple Inc", "Information Technology", 3e12),
    SP500Stock("MSFT", "Microsoft", "Information Technology", 2.8e12),
    SP500Stock("AMZN", "Amazon", "Consumer Discretionary", 1.8e12),
    SP500Stock("NVDA", "NVIDIA", "Information Technology", 1.5e12),
    SP500Stock("GOOGL", "Alphabet", "Communication Services", 1.7e12),
    SP500Stock("META", "Meta Platforms", "Communication Services", 1.2e12),
    SP500Stock("BRK-B", "Berkshire Hathaway", "Financials", 800e9),
    SP500Stock("TSLA", "Tesla", "Consumer Discretionary", 700e9),
    SP500Stock("UNH", "UnitedHealth", "Health Care", 500e9),
    SP500Stock("JNJ", "Johnson & Johnson", "Health Care", 450e9),
    SP500Stock("JPM", "JPMorgan Chase", "Financials", 450e9),
    SP500Stock("V", "Visa", "Financials", 400e9),
    SP500Stock("XOM", "Exxon Mobil", "Energy", 400e9),
    SP500Stock("PG", "Procter & Gamble", "Consumer Staples", 370e9),
    SP500Stock("MA", "Mastercard", "Financials", 360e9),
    SP500Stock("HD", "Home Depot", "Consumer Discretionary", 350e9),
    SP500Stock("CVX", "Chevron", "Energy", 300e9),
    SP500Stock("COST", "Costco", "Consumer Staples", 280e9),
    SP500Stock("WMT", "Walmart", "Consumer Staples", 450e9),
    SP500Stock("BAC", "Bank of America", "Financials", 250e9),
    SP500Stock("AMD", "Advanced Micro Devices", "Information Technology", 200e9),
    SP500Stock("INTC", "Intel", "Information Technology", 150e9),
    SP500Stock("DIS", "Walt Disney", "Communication Services", 180e9),
    SP500Stock("CRM", "Salesforce", "Information Technology", 250e9),
    SP500Stock("NFLX", "Netflix", "Communication Services", 230e9),
]


async def get_sp500() -> list[SP500Stock]:
    """Get S&P 500 universe."""
    cache_key = "universe:sp500"
    cached = await cache_get(cache_key)
    if cached:
        return [SP500Stock(**s) for s in cached]

    from dataclasses import asdict
    await cache_set(cache_key, [asdict(s) for s in SP500_CORE], UNIVERSE_CACHE_TTL)
    return SP500_CORE


async def get_sp500_symbols() -> list[str]:
    stocks = await get_sp500()
    return [s.symbol for s in stocks]


def is_sp500_member(symbol: str) -> bool:
    """Check if symbol is in S&P 500 (IHVV overlap)."""
    return symbol in {s.symbol for s in SP500_CORE}
