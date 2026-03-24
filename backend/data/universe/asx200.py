"""ASX 200 universe manager."""

import logging
from typing import Optional
from dataclasses import dataclass

from backend.data.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

UNIVERSE_CACHE_TTL = 604800  # 7 days


@dataclass
class UniverseStock:
    symbol: str
    company_name: str
    gics_sector: str
    market_cap_aud: float
    index_weight: float


# Top ASX 200 constituents (representative sample for initial operation)
# In production, this would be scraped from ASX website weekly
ASX200_CORE = [
    UniverseStock("BHP", "BHP Group", "Materials", 230e9, 10.5),
    UniverseStock("CBA", "Commonwealth Bank", "Financials", 200e9, 9.8),
    UniverseStock("CSL", "CSL Limited", "Health Care", 130e9, 6.5),
    UniverseStock("NAB", "National Australia Bank", "Financials", 100e9, 4.2),
    UniverseStock("WBC", "Westpac Banking", "Financials", 85e9, 3.8),
    UniverseStock("ANZ", "ANZ Group", "Financials", 80e9, 3.5),
    UniverseStock("WES", "Wesfarmers", "Consumer Discretionary", 75e9, 3.3),
    UniverseStock("MQG", "Macquarie Group", "Financials", 70e9, 3.1),
    UniverseStock("FMG", "Fortescue", "Materials", 65e9, 2.8),
    UniverseStock("WOW", "Woolworths Group", "Consumer Staples", 45e9, 2.2),
    UniverseStock("RIO", "Rio Tinto", "Materials", 42e9, 1.9),
    UniverseStock("TLS", "Telstra Group", "Communication Services", 40e9, 1.8),
    UniverseStock("ALL", "Aristocrat Leisure", "Consumer Discretionary", 38e9, 1.7),
    UniverseStock("TCL", "Transurban Group", "Industrials", 37e9, 1.6),
    UniverseStock("GMG", "Goodman Group", "Real Estate", 36e9, 1.5),
    UniverseStock("WDS", "Woodside Energy", "Energy", 35e9, 1.5),
    UniverseStock("STO", "Santos", "Energy", 20e9, 0.9),
    UniverseStock("COL", "Coles Group", "Consumer Staples", 22e9, 1.0),
    UniverseStock("REA", "REA Group", "Communication Services", 21e9, 0.9),
    UniverseStock("QBE", "QBE Insurance", "Financials", 20e9, 0.9),
    UniverseStock("SHL", "Sonic Healthcare", "Health Care", 18e9, 0.8),
    UniverseStock("NCM", "Newcrest Mining", "Materials", 17e9, 0.8),
    UniverseStock("ORG", "Origin Energy", "Energy", 16e9, 0.7),
    UniverseStock("S32", "South32", "Materials", 14e9, 0.6),
    UniverseStock("CPU", "Computershare", "Information Technology", 13e9, 0.6),
    UniverseStock("JHX", "James Hardie", "Materials", 12e9, 0.5),
    UniverseStock("MIN", "Mineral Resources", "Materials", 11e9, 0.5),
    UniverseStock("XRO", "Xero", "Information Technology", 10e9, 0.5),
    UniverseStock("WTC", "WiseTech Global", "Information Technology", 9e9, 0.4),
    UniverseStock("RMD", "ResMed", "Health Care", 8e9, 0.4),
]


async def get_asx200() -> list[UniverseStock]:
    """Get ASX 200 universe. Cached for 7 days."""
    cache_key = "universe:asx200"
    cached = await cache_get(cache_key)
    if cached:
        return [UniverseStock(**s) for s in cached]

    # In production: scrape from ASX website
    # For now, use static list
    stocks = ASX200_CORE

    from dataclasses import asdict
    await cache_set(cache_key, [asdict(s) for s in stocks], UNIVERSE_CACHE_TTL)
    return stocks


async def get_asx200_symbols() -> list[str]:
    """Get just the symbols."""
    stocks = await get_asx200()
    return [s.symbol for s in stocks]


def is_top50_asx300(symbol: str) -> bool:
    """Check if symbol is a significant ASX 300 constituent (VAS overlap)."""
    top50 = {s.symbol for s in ASX200_CORE[:50]}
    return symbol in top50
