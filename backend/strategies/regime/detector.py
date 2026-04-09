"""Market regime detection and strategy gating.

Classifies market conditions into one of five regimes and determines
which strategies should be active or suppressed.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from backend.data.cache import cache_get, cache_set
from backend.data.feeds.yfinance_feed import get_daily_bars
from backend.data.feeds.fred_feed import get_vix, get_yield_spread

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    STRONG_TREND_BULL = "STRONG_TREND_BULL"
    MODERATE_TREND_BULL = "MODERATE_TREND_BULL"
    CHOPPY_RANGE_BOUND = "CHOPPY_RANGE_BOUND"
    RISK_OFF_ELEVATED_FEAR = "RISK_OFF_ELEVATED_FEAR"
    CRISIS_EXTREME_FEAR = "CRISIS_EXTREME_FEAR"


@dataclass
class RegimeSnapshot:
    market: str
    regime: MarketRegime
    vix: Optional[float]
    index_adx: Optional[float]
    breadth_pct: Optional[float]
    yield_spread: Optional[float]
    ad_ratio: Optional[float]
    strategies_active: list[str]
    strategies_suppressed: list[str]
    recorded_at: datetime


# Which strategies are allowed in each regime
REGIME_STRATEGY_MAP = {
    MarketRegime.STRONG_TREND_BULL: {
        "active": ["dual_momentum", "trend_following", "breakout",
                    "sector_rotation", "fundamental_screen", "earnings_catalyst"],
        "suppressed": ["bollinger_rsi", "gap_fade", "pairs_scanner"],
    },
    MarketRegime.MODERATE_TREND_BULL: {
        "active": ["dual_momentum", "trend_following", "breakout",
                    "bollinger_rsi", "pairs_scanner", "gap_fade",
                    "fundamental_screen", "earnings_catalyst", "sector_rotation"],
        "suppressed": [],
    },
    MarketRegime.CHOPPY_RANGE_BOUND: {
        "active": ["bollinger_rsi", "pairs_scanner", "fundamental_screen",
                    "earnings_catalyst", "sector_rotation", "gap_fade"],
        "suppressed": ["dual_momentum", "trend_following", "breakout"],
    },
    MarketRegime.RISK_OFF_ELEVATED_FEAR: {
        "active": ["fundamental_screen", "sector_rotation", "pairs_scanner"],
        "suppressed": ["dual_momentum", "trend_following", "breakout", "gap_fade"],
    },
    MarketRegime.CRISIS_EXTREME_FEAR: {
        "active": ["fundamental_screen"],
        "suppressed": ["dual_momentum", "trend_following", "breakout",
                       "bollinger_rsi", "pairs_scanner", "gap_fade",
                       "earnings_catalyst", "sector_rotation"],
    },
}


def compute_adx(bars: list, period: int = 14) -> Optional[float]:
    """Compute ADX from OHLCV bars."""
    if len(bars) < period * 2:
        return None

    highs = np.array([b.high for b in bars])
    lows = np.array([b.low for b in bars])
    closes = np.array([b.close for b in bars])

    # True Range
    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:] - closes[:-1])
        )
    )

    # +DM, -DM
    plus_dm = np.where(
        (highs[1:] - highs[:-1]) > (lows[:-1] - lows[1:]),
        np.maximum(highs[1:] - highs[:-1], 0),
        0
    )
    minus_dm = np.where(
        (lows[:-1] - lows[1:]) > (highs[1:] - highs[:-1]),
        np.maximum(lows[:-1] - lows[1:], 0),
        0
    )

    # Smoothed averages (Wilder's method)
    atr = np.zeros(len(tr))
    plus_di = np.zeros(len(tr))
    minus_di = np.zeros(len(tr))

    atr[period - 1] = np.mean(tr[:period])
    s_plus_dm = np.mean(plus_dm[:period])
    s_minus_dm = np.mean(minus_dm[:period])

    for i in range(period, len(tr)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        s_plus_dm = (s_plus_dm * (period - 1) + plus_dm[i]) / period
        s_minus_dm = (s_minus_dm * (period - 1) + minus_dm[i]) / period

        if atr[i] > 0:
            plus_di[i] = 100 * s_plus_dm / atr[i]
            minus_di[i] = 100 * s_minus_dm / atr[i]

    # DX and ADX
    dx = np.zeros(len(tr))
    for i in range(period, len(tr)):
        denom = plus_di[i] + minus_di[i]
        if denom > 0:
            dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / denom

    # ADX = smoothed DX
    if len(dx) < period * 2:
        return None

    adx_start = period * 2 - 1
    adx = np.mean(dx[period:adx_start + 1])
    for i in range(adx_start + 1, len(dx)):
        adx = (adx * (period - 1) + dx[i]) / period

    return round(float(adx), 2)


def compute_breadth(bars_list: list[list]) -> float:
    """Compute market breadth: % of stocks above their 50-day SMA."""
    above_sma = 0
    total = 0

    for bars in bars_list:
        if len(bars) < 50:
            continue
        closes = [b.close for b in bars]
        sma50 = np.mean(closes[-50:])
        current = closes[-1]
        total += 1
        if current > sma50:
            above_sma += 1

    return round(above_sma / total, 3) if total > 0 else 0.5


def classify_regime(
    vix: Optional[float],
    adx: Optional[float],
    breadth: Optional[float],
    ad_ratio: Optional[float] = None,
) -> MarketRegime:
    """Classify market regime from indicators."""
    # Default safe values
    vix = vix or 18.0
    adx = adx or 20.0
    breadth = breadth or 0.50
    ad_ratio = ad_ratio or 1.0

    # Crisis first — highest priority
    if vix > 30 and breadth < 0.35:
        return MarketRegime.CRISIS_EXTREME_FEAR

    # Risk off
    if vix > 20 and breadth < 0.45 and ad_ratio < 0.7:
        return MarketRegime.RISK_OFF_ELEVATED_FEAR

    # Strong trend bull
    if adx > 25 and breadth > 0.65 and vix < 15:
        return MarketRegime.STRONG_TREND_BULL

    # Choppy
    if adx < 18 and 0.40 <= breadth <= 0.55 and 15 <= vix <= 25:
        return MarketRegime.CHOPPY_RANGE_BOUND

    # Default: moderate bull
    return MarketRegime.MODERATE_TREND_BULL


def is_strategy_active(strategy_name: str, regime: MarketRegime) -> bool:
    """Check if a strategy should run in the current regime."""
    mapping = REGIME_STRATEGY_MAP.get(regime, REGIME_STRATEGY_MAP[MarketRegime.MODERATE_TREND_BULL])
    return strategy_name in mapping["active"]


def get_active_strategies(regime: MarketRegime) -> list[str]:
    """Get list of active strategy names for a regime."""
    return REGIME_STRATEGY_MAP.get(regime, {}).get("active", [])


def get_suppressed_strategies(regime: MarketRegime) -> list[str]:
    """Get list of suppressed strategy names for a regime."""
    return REGIME_STRATEGY_MAP.get(regime, {}).get("suppressed", [])


async def detect_regime(market: str) -> RegimeSnapshot:
    """Detect current market regime. Cached in Redis for 30 min."""
    cache_key = f"market_regime:{market}"
    cached = await cache_get(cache_key)
    if cached:
        return RegimeSnapshot(
            market=cached["market"],
            regime=MarketRegime(cached["regime"]),
            vix=cached.get("vix"),
            index_adx=cached.get("index_adx"),
            breadth_pct=cached.get("breadth_pct"),
            yield_spread=cached.get("yield_spread"),
            ad_ratio=cached.get("ad_ratio"),
            strategies_active=cached.get("strategies_active", []),
            strategies_suppressed=cached.get("strategies_suppressed", []),
            recorded_at=datetime.fromisoformat(cached["recorded_at"]),
        )

    # Collect indicators
    vix = await get_vix()
    spread = await get_yield_spread()

    # Get index bars for ADX
    if market == "ASX":
        index_symbol = "^AXJO"
    else:
        index_symbol = "^GSPC"

    # Get index bars from DataRouter for ADX calculation
    adx_value = None
    try:
        # Twelve Data symbols: XJO for ASX200, SPX for S&P 500
        router_symbol = "XJO" if market == "ASX" else "SPX"
        from backend.data.feeds.data_router import get_data_router
        bars = await get_data_router().get_ohlcv(router_symbol, market, "1day", 90)
        if bars:
            adx_value = compute_adx(bars)
    except Exception as e:
        logger.error("Failed to compute ADX for %s: %s", market, e)

    # Breadth would require scanning all stocks — use estimate for now
    breadth = 0.55  # Placeholder — computed in full scan cycle

    regime = classify_regime(vix, adx_value, breadth)

    snapshot = RegimeSnapshot(
        market=market,
        regime=regime,
        vix=vix,
        index_adx=adx_value,
        breadth_pct=breadth,
        yield_spread=spread,
        ad_ratio=None,
        strategies_active=get_active_strategies(regime),
        strategies_suppressed=get_suppressed_strategies(regime),
        recorded_at=datetime.now(timezone.utc),
    )

    # Cache for 30 minutes
    await cache_set(cache_key, {
        "market": snapshot.market,
        "regime": snapshot.regime.value,
        "vix": snapshot.vix,
        "index_adx": snapshot.index_adx,
        "breadth_pct": snapshot.breadth_pct,
        "yield_spread": snapshot.yield_spread,
        "ad_ratio": snapshot.ad_ratio,
        "strategies_active": snapshot.strategies_active,
        "strategies_suppressed": snapshot.strategies_suppressed,
        "recorded_at": snapshot.recorded_at.isoformat(),
    }, 1800)

    return snapshot


async def get_current_regime(market: str) -> MarketRegime:
    """Convenience: get just the regime enum."""
    snapshot = await detect_regime(market)
    return snapshot.regime
