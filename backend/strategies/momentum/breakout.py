"""Consolidation Breakout strategy.

Identifies stocks consolidating in a tight range within an uptrend,
then breaking out on volume.
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


class Breakout(BaseStrategy):
    name = "breakout"
    weight = 1.2

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
        ideas = []

        for stock in universe:
            try:
                bars = await get_daily_bars(stock.symbol, market, period="6mo")
                if len(bars) < 60:
                    continue

                idea = self._evaluate(stock, bars, market)
                if idea:
                    ideas.append(idea)

            except Exception as e:
                logger.error("Breakout error for %s: %s", stock.symbol, e)

        return ideas

    def _evaluate(self, stock, bars, market) -> Optional[TradeIdea]:
        closes = np.array([b.close for b in bars])
        highs = np.array([b.high for b in bars])
        lows = np.array([b.low for b in bars])
        volumes = np.array([b.volume for b in bars])

        current = closes[-1]
        sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else None
        sma200 = np.mean(closes[-200:]) if len(closes) >= 200 else np.mean(closes)

        # Uptrend: Price > 50 SMA > 200 SMA
        if sma50 is None or current < sma50 or sma50 < sma200:
            return None

        # ATR contraction: current ATR < 70% of 20-day average ATR
        atr_current = self._atr_single(bars, 5)
        atr_avg = self._atr_single(bars, 20)
        if atr_current is None or atr_avg is None or atr_avg == 0:
            return None
        if atr_current / atr_avg > 0.70:
            return None  # Not contracted enough

        # Tight range: look for 5-20 day consolidation
        lookback_range = 15
        recent_highs = highs[-lookback_range:]
        recent_lows = lows[-lookback_range:]
        consolidation_high = np.max(recent_highs)
        consolidation_low = np.min(recent_lows)
        consolidation_range = consolidation_high - consolidation_low

        # Range must be < 2x ATR
        if consolidation_range > 2 * atr_avg:
            return None

        # Volume declining during consolidation
        vol_first_half = np.mean(volumes[-lookback_range:-lookback_range // 2])
        vol_second_half = np.mean(volumes[-lookback_range // 2:])
        if vol_second_half > vol_first_half * 1.1:
            return None  # Volume should be declining

        # Breakout trigger: close above consolidation high + volume
        if current < consolidation_high:
            return None  # No breakout yet

        avg_vol = np.mean(volumes[-20:])
        if volumes[-1] < avg_vol * 1.2:
            return None  # Need volume confirmation

        # Entry, stop, targets
        entry = round(consolidation_high + consolidation_high * 0.001, 4)
        stop = round(consolidation_low - consolidation_low * 0.003, 4)
        risk = entry - stop
        if risk <= 0:
            return None

        # Measured move target (range height projected up)
        target_1 = round(entry + consolidation_range, 4)
        target_2 = round(entry + 2 * consolidation_range, 4)
        target_3 = round(entry + 3 * consolidation_range, 4)
        rr = round((target_2 - entry) / risk, 2) if risk > 0 else 0

        sizing = compute_sizing(
            entry, stop, market,
            settings.portfolio_value_aud,
            settings.risk_per_trade_pct,
        )

        # Detect pattern
        pattern = self._detect_pattern(recent_highs, recent_lows, closes[-lookback_range:])

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
            conviction=Conviction.HIGH if rr > 3 else Conviction.MEDIUM,
            time_horizon=TimeHorizon.SWING,
            current_price=round(current, 4),
            suggested_entry=entry,
            entry_range_low=round(entry * 0.998, 4),
            entry_range_high=round(entry * 1.005, 4),
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
                f"Consolidation breakout: {pattern}",
                f"ATR contraction: {atr_current/atr_avg*100:.0f}% of average",
                f"Volume on breakout: {volumes[-1]/avg_vol:.1f}x average",
            ],
            technical_summary=(
                f"{pattern} pattern breakout above {consolidation_high:.2f}. "
                f"ATR contracted to {atr_current/atr_avg*100:.0f}% of normal. "
                f"Volume confirmation at {volumes[-1]/avg_vol:.1f}x."
            ),
            risk_factors=[
                "False breakout risk — price may re-enter range",
                f"Stop below consolidation low at {stop:.2f}",
            ],
            invalidation_conditions=[
                f"Price closes below consolidation low ({consolidation_low:.2f})",
                "Volume dries up within 2 days of breakout",
            ],
            indicators={
                "consolidation_high": round(consolidation_high, 4),
                "consolidation_low": round(consolidation_low, 4),
                "atr_contraction": round(atr_current / atr_avg, 3),
                "volume_ratio": round(volumes[-1] / avg_vol, 2),
            },
            chart_patterns=[pattern],
            vas_overlap=vas_overlap,
            ihvv_overlap=ihvv_overlap,
        )

    @staticmethod
    def _atr_single(bars, period):
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

    @staticmethod
    def _detect_pattern(highs, lows, closes):
        """Simple pattern detection."""
        high_slope = np.polyfit(range(len(highs)), highs, 1)[0]
        low_slope = np.polyfit(range(len(lows)), lows, 1)[0]

        if abs(high_slope) < 0.01 and abs(low_slope) < 0.01:
            return "flat base"
        elif high_slope < -0.01 and low_slope > 0.01:
            return "symmetrical triangle"
        elif abs(high_slope) < 0.01 and low_slope > 0.01:
            return "ascending triangle"
        elif high_slope < -0.01:
            return "bull flag"
        else:
            return "consolidation"
