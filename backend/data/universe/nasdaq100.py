"""NASDAQ 100 universe manager."""

from dataclasses import dataclass
from backend.data.cache import cache_get, cache_set

UNIVERSE_CACHE_TTL = 604800


@dataclass
class Nasdaq100Stock:
    symbol: str
    company_name: str
    gics_sector: str


NASDAQ100_CORE = [
    Nasdaq100Stock("AAPL", "Apple", "Information Technology"),
    Nasdaq100Stock("MSFT", "Microsoft", "Information Technology"),
    Nasdaq100Stock("AMZN", "Amazon", "Consumer Discretionary"),
    Nasdaq100Stock("NVDA", "NVIDIA", "Information Technology"),
    Nasdaq100Stock("GOOGL", "Alphabet", "Communication Services"),
    Nasdaq100Stock("META", "Meta Platforms", "Communication Services"),
    Nasdaq100Stock("TSLA", "Tesla", "Consumer Discretionary"),
    Nasdaq100Stock("AMD", "AMD", "Information Technology"),
    Nasdaq100Stock("NFLX", "Netflix", "Communication Services"),
    Nasdaq100Stock("INTC", "Intel", "Information Technology"),
    Nasdaq100Stock("CRM", "Salesforce", "Information Technology"),
    Nasdaq100Stock("QCOM", "Qualcomm", "Information Technology"),
    Nasdaq100Stock("AVGO", "Broadcom", "Information Technology"),
    Nasdaq100Stock("ADBE", "Adobe", "Information Technology"),
    Nasdaq100Stock("PYPL", "PayPal", "Financials"),
]


async def get_nasdaq100() -> list[Nasdaq100Stock]:
    cache_key = "universe:nasdaq100"
    cached = await cache_get(cache_key)
    if cached:
        return [Nasdaq100Stock(**s) for s in cached]

    from dataclasses import asdict
    await cache_set(cache_key, [asdict(s) for s in NASDAQ100_CORE], UNIVERSE_CACHE_TTL)
    return NASDAQ100_CORE


async def get_nasdaq100_symbols() -> list[str]:
    stocks = await get_nasdaq100()
    return [s.symbol for s in stocks]
