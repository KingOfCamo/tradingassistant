"""Gap Fade strategy.

Fades large opening gaps that lack fundamental catalysts.
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


class GapFade(BaseStrategy):
    name = "gap_fade"
    weight = 0.7

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
        ideas = []
        for stock in universe:
            try:
                bars = await get_daily_bars(stock.symbol, market, period="1mo")
                if len(bars) < 10:
                    continue
                idea = self._evaluate(stock, bars, market)
                if idea:
                    ideas.append(idea)
            except Exception as e:
                logger.error("GapFade error for %s: %s", stock.symbol, e)
        return ideas

    def _evaluate(self, stock, bars, market) -> Optional[TradeIdea]:
        if len(bars) < 6:
            return None

        prev_close = bars[-2].close
        today_open = bars[-1].open
        current = bars[-1].close
        volumes = np.array([b.volume for b in bars])

        gap_pct = ((today_open - prev_close) / prev_close) * 100

        # Need gap > 2%
        if abs(gap_pct) < 2.0:
            return None

        # Volume confirmation
        avg_vol = np.mean(volumes[-10:-1]) if len(volumes) > 10 else np.mean(volumes[:-1])
        if bars[-1].volume < avg_vol * 1.5:
            return None

        # 5-day prior trend
        five_day_trend = (bars[-2].close / bars[-6].close - 1) * 100

        if gap_pct < -2.0:
            # Gap down — potential long
            if five_day_trend < 0:
                return None  # Prior trend was already down
            direction = Direction.LONG
            entry = round(today_open * 1.002, 4)
            stop = round(today_open * (1 - abs(gap_pct) / 200), 4)
            target = round(prev_close, 4)
        elif gap_pct > 2.0 and market != "ASX":
            # Gap up — potential short (US only)
            if five_day_trend > 0:
                return None
            direction = Direction.SHORT
            entry = round(today_open * 0.998, 4)
            stop = round(today_open * (1 + abs(gap_pct) / 200), 4)
            target = round(prev_close, 4)
        else:
            return None

        risk = abs(entry - stop)
        if risk == 0:
            return None
        rr = round(abs(target - entry) / risk, 2)

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
            direction=direction,
            conviction=Conviction.MEDIUM if rr > 1.5 else Conviction.LOW,
            time_horizon=TimeHorizon.INTRADAY,
            current_price=round(current, 4),
            suggested_entry=entry,
            entry_range_low=round(entry * 0.998, 4),
            entry_range_high=round(entry * 1.002, 4),
            stop_loss=stop,
            target_1=target,
            target_2=round((target + entry) / 2, 4),
            target_3=target,
            risk_reward_ratio=rr,
            suggested_shares=sizing["shares"],
            position_value_aud=sizing["position_value_aud"],
            risk_amount_aud=sizing["risk_amount_aud"],
            cmc_brokerage_aud=sizing["brokerage_aud"],
            cmc_fx_cost_aud=sizing["fx_cost_aud"],
            total_trade_cost_aud=sizing["total_cost_aud"],
            small_trade_warning=sizing["small_trade_warning"],
            key_factors=[
                f"Gap {'down' if gap_pct < 0 else 'up'}: {gap_pct:.1f}%",
                f"Target: previous close ({prev_close:.2f})",
                "Exit by midday",
            ],
            technical_summary=f"Gap fade: {gap_pct:.1f}% gap, targeting previous close at {prev_close:.2f}.",
            risk_factors=["Gap may continue", "Intraday time pressure"],
            invalidation_conditions=["Gap extends beyond stop", "No reversal by midday"],
            indicators={"gap_pct": round(gap_pct, 2), "volume_ratio": round(bars[-1].volume / avg_vol, 2)},
        )
