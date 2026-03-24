"""Trend Following strategy (Modernised Turtle).

Donchian channel breakout with trend quality filters.
"""

import logging
from typing import Optional

import numpy as np

from backend.strategies.base import (
    BaseStrategy, TradeIdea, Direction, Conviction, TimeHorizon,
    compute_sizing,
)
from backend.data.feeds.yfinance_feed import get_daily_bars
from backend.data.universe.asx200 import is_top50_asx300
from backend.data.universe.sp500 import is_sp500_member
from backend.config import settings

logger = logging.getLogger(__name__)


class TrendFollowing(BaseStrategy):
    name = "trend_following"
    weight = 1.3

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
        ideas = []

        for stock in universe:
            try:
                bars = await get_daily_bars(stock.symbol, market, period="6mo")
                if len(bars) < 90:
                    continue

                idea = self._evaluate(stock, bars, market)
                if idea:
                    ideas.append(idea)

            except Exception as e:
                logger.error("TrendFollowing error for %s: %s", stock.symbol, e)

        return ideas

    def _evaluate(self, stock, bars, market) -> Optional[TradeIdea]:
        closes = np.array([b.close for b in bars])
        highs = np.array([b.high for b in bars])
        lows = np.array([b.low for b in bars])
        volumes = np.array([b.volume for b in bars])

        if len(closes) < 90:
            return None

        current = closes[-1]

        # 20-day Donchian high
        donchian_high_20 = np.max(highs[-20:])

        # Must have broken above Donchian high today
        if current < donchian_high_20 * 0.998:  # Within 0.2%
            return None

        # Volume confirmation: > 1.5x average
        avg_vol = np.mean(volumes[-20:])
        if volumes[-1] < avg_vol * 1.5:
            return None

        # Trend quality: 2 of 3 conditions
        sma200 = np.mean(closes[-200:]) if len(closes) >= 200 else np.mean(closes)
        trend_checks = 0

        # MACD positive
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        if ema12 > ema26:
            trend_checks += 1

        # Price > 200 SMA
        if current > sma200:
            trend_checks += 1

        # Weekly RSI > 50 (approximate with 5-day)
        rsi = self._rsi(closes)
        if rsi and rsi > 50:
            trend_checks += 1

        if trend_checks < 2:
            return None

        # ATR/price filter (volatility not too high)
        atr = self._atr(bars)
        if atr and (atr / current * 100) > 5:
            return None

        # Market cap filter
        mcap = getattr(stock, 'market_cap_aud', None) or getattr(stock, 'market_cap_usd', 0)
        min_mcap = 300e6 if market == "ASX" else 1e9
        if mcap and mcap < min_mcap:
            return None

        # Stop: 2x ATR below entry
        entry = round(current, 4)
        stop = round(entry - 2 * atr, 4) if atr else round(entry * 0.95, 4)
        risk = entry - stop

        target_1 = round(entry + 1.5 * risk, 4)
        target_2 = round(entry + 3 * risk, 4)
        target_3 = round(entry + 5 * risk, 4)
        rr = round((target_2 - entry) / risk, 2) if risk > 0 else 0

        sizing = compute_sizing(
            entry, stop, market,
            settings.portfolio_value_aud,
            settings.risk_per_trade_pct,
        )

        vas_overlap = is_top50_asx300(stock.symbol) if market == "ASX" else False
        ihvv_overlap = is_sp500_member(stock.symbol) if market != "ASX" else False

        return TradeIdea(
            symbol=stock.symbol,
            company_name=stock.company_name,
            market=market,
            sector=stock.gics_sector,
            is_etf=False,
            strategy_name=self.name,
            direction=Direction.LONG,
            conviction=Conviction.MEDIUM,
            time_horizon=TimeHorizon.SWING,
            current_price=current,
            suggested_entry=entry,
            entry_range_low=round(entry * 0.99, 4),
            entry_range_high=round(entry * 1.01, 4),
            stop_loss=stop,
            target_1=target_1,
            target_2=target_2,
            target_3=target_3,
            risk_reward_ratio=rr,
            suggested_shares=sizing["shares"],
            position_value_aud=sizing["position_value_aud"],
            risk_amount_aud=sizing["risk_amount_aud"],
            cmc_brokerage_aud=sizing["brokerage_aud"],
            cmc_fx_cost_aud=sizing["fx_cost_aud"],
            total_trade_cost_aud=sizing["total_cost_aud"],
            small_trade_warning=sizing["small_trade_warning"],
            key_factors=[
                f"20-day Donchian breakout at {donchian_high_20:.2f}",
                f"Volume {volumes[-1]/avg_vol:.1f}x average",
                f"Trend quality: {trend_checks}/3 checks passed",
            ],
            technical_summary=(
                f"Donchian channel breakout with {volumes[-1]/avg_vol:.1f}x volume. "
                f"Trend confirmed ({trend_checks}/3 quality checks)."
            ),
            risk_factors=[
                "False breakout risk — volume must sustain",
                f"Stop at 2x ATR ({stop:.2f})",
            ],
            invalidation_conditions=[
                f"Price closes below {stop:.2f}",
                "Volume drops below average for 3 consecutive days",
            ],
            indicators={
                "donchian_high_20": round(donchian_high_20, 4),
                "volume_ratio": round(volumes[-1] / avg_vol, 2),
                "rsi": round(rsi, 2) if rsi else None,
                "atr": round(atr, 4) if atr else None,
                "trend_quality": trend_checks,
            },
            vas_overlap=vas_overlap,
            ihvv_overlap=ihvv_overlap,
        )

    @staticmethod
    def _ema(data, period):
        if len(data) < period:
            return data[-1]
        multiplier = 2 / (period + 1)
        ema = np.mean(data[:period])
        for val in data[period:]:
            ema = (val - ema) * multiplier + ema
        return ema

    @staticmethod
    def _rsi(closes, period=14):
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        if avg_loss == 0:
            return 100.0
        return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)

    @staticmethod
    def _atr(bars, period=14):
        if len(bars) < period + 1:
            return None
        trs = []
        for i in range(1, min(period + 1, len(bars))):
            tr = max(
                bars[-i].high - bars[-i].low,
                abs(bars[-i].high - bars[-i - 1].close),
                abs(bars[-i].low - bars[-i - 1].close),
            )
            trs.append(tr)
        return np.mean(trs)
