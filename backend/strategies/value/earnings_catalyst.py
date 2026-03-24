"""Earnings Catalyst strategy.

Pre-earnings momentum and post-earnings drift detection.
"""

import logging
from typing import Optional
import numpy as np

from backend.strategies.base import (
    BaseStrategy, TradeIdea, Direction, Conviction, TimeHorizon, compute_sizing,
)
from backend.data.feeds.yfinance_feed import get_daily_bars
from backend.config import settings

logger = logging.getLogger(__name__)


class EarningsCatalyst(BaseStrategy):
    name = "earnings_catalyst"
    weight = 1.1

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
        ideas = []
        for stock in universe:
            try:
                bars = await get_daily_bars(stock.symbol, market, period="3mo")
                if len(bars) < 30:
                    continue
                idea = self._evaluate(stock, bars, market)
                if idea:
                    ideas.append(idea)
            except Exception as e:
                logger.error("EarningsCatalyst error for %s: %s", stock.symbol, e)
        return ideas

    def _evaluate(self, stock, bars, market) -> Optional[TradeIdea]:
        closes = np.array([b.close for b in bars])
        volumes = np.array([b.volume for b in bars])
        current = closes[-1]

        # Check for momentum into potential catalyst
        ret_1m = (current / closes[-22] - 1) * 100 if len(closes) > 22 else 0

        # Positive momentum but not already overextended
        if ret_1m < 2 or ret_1m > 15:
            return None

        # Volume increasing (interest building)
        vol_recent = np.mean(volumes[-5:])
        vol_prior = np.mean(volumes[-20:-5]) if len(volumes) > 20 else np.mean(volumes[:-5])
        if vol_recent < vol_prior * 1.1:
            return None

        # Not already at 52-week high
        high_52w = max(b.high for b in bars)
        if current > high_52w * 0.97:
            return None

        entry = round(current, 4)
        atr = self._atr(bars)
        stop = round(entry - 2 * atr, 4) if atr else round(entry * 0.95, 4)
        risk = entry - stop
        if risk <= 0:
            return None

        target_1 = round(entry * 1.05, 4)
        target_2 = round(entry * 1.10, 4)
        target_3 = round(high_52w, 4)

        sizing = compute_sizing(
            entry, stop, market,
            settings.portfolio_value_aud, settings.risk_per_trade_pct,
        )

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
            risk_reward_ratio=round((target_2 - entry) / risk, 2) if risk > 0 else 0,
            suggested_shares=sizing["shares"],
            position_value_aud=sizing["position_value_aud"],
            risk_amount_aud=sizing["risk_amount_aud"],
            cmc_brokerage_aud=sizing["brokerage_aud"],
            cmc_fx_cost_aud=sizing["fx_cost_aud"],
            total_trade_cost_aud=sizing["total_cost_aud"],
            small_trade_warning=sizing["small_trade_warning"],
            key_factors=[
                f"1-month momentum: +{ret_1m:.1f}%",
                f"Volume building: {vol_recent/vol_prior:.1f}x",
                "Potential earnings catalyst",
            ],
            technical_summary=f"Pre-catalyst momentum: +{ret_1m:.1f}% with {vol_recent/vol_prior:.1f}x volume.",
            risk_factors=["Earnings miss risk", "Sell-the-news potential"],
            invalidation_conditions=[f"Price drops below {stop:.2f}", "Negative pre-announcement"],
            indicators={"ret_1m": round(ret_1m, 2), "volume_building": round(vol_recent / vol_prior, 2)},
        )

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
