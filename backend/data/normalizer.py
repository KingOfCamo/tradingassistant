"""Normalized data structures for market data."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class OHLCV:
    symbol: str           # Always without .AX suffix internally
    market: str           # 'ASX' | 'NYSE' | 'NASDAQ'
    timestamp: datetime   # Always UTC
    open: float
    high: float
    low: float
    close: float
    volume: int
    adj_close: Optional[float] = None
    vwap: Optional[float] = None


@dataclass
class Quote:
    symbol: str
    market: str
    price: float
    change: float
    change_pct: float
    volume: int
    avg_volume_20d: int
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
