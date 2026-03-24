"""Dual Momentum strategy (Gary Antonacci).

Absolute + relative momentum with quality filters.
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


class DualMomentum(BaseStrategy):
    name = "dual_momentum"
    weight = 1.5

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
        ideas = []

        for stock in universe:
            try:
                bars = await get_daily_bars(stock.symbol, market, period="1y")
                if len(bars) < 252:
                    continue

                closes = np.array([b.close for b in bars])
                volumes = np.array([b.volume for b in bars])

                idea = self._evaluate(stock, bars, closes, volumes, market)
                if idea:
                    ideas.append(idea)

            except Exception as e:
                logger.error("DualMomentum error for %s: %s", stock.symbol, e)

        # Rank by momentum score, take top 15
        ideas.sort(key=lambda x: x.indicators.get("momentum_score", 0), reverse=True)
        return ideas[:15]

    def _evaluate(self, stock, bars, closes, volumes, market) -> Optional[TradeIdea]:
        """Evaluate a single stock against dual momentum criteria."""
        if len(closes) < 252:
            return None

        # Momentum scores (12m-ex-1m, 6m-ex-1m, 3m, 1m)
        ret_12m = (closes[-22] / closes[0] - 1) if closes[0] > 0 else 0  # 12m ex last month
        ret_6m = (closes[-22] / closes[-132] - 1) if closes[-132] > 0 else 0
        ret_3m = (closes[-1] / closes[-63] - 1) if closes[-63] > 0 else 0
        ret_1m = (closes[-1] / closes[-22] - 1) if closes[-22] > 0 else 0

        momentum_score = ret_12m * 0.4 + ret_6m * 0.3 + ret_3m * 0.2 + ret_1m * 0.1

        # Absolute momentum: must beat risk-free rate
        if ret_12m < 0.04:  # ~4% annual risk-free threshold
            return None

        # Quality filters
        current = closes[-1]
        sma200 = np.mean(closes[-200:])
        sma50 = np.mean(closes[-50:])

        if current < sma200 or current < sma50:
            return None
        if sma50 < sma200:  # 50 SMA must be above 200 SMA
            return None

        # Volume filter
        avg_volume = np.mean(volumes[-20:])
        avg_dollar_vol = avg_volume * current
        min_dollar_vol = 500_000 if market == "ASX" else 5_000_000
        if avg_dollar_vol < min_dollar_vol:
            return None

        # RSI check (50-75 range)
        rsi = self._compute_rsi(closes)
        if rsi is None or rsi < 50 or rsi > 75:
            return None

        # ADX check
        adx = self._compute_simple_adx(bars)
        if adx is not None and adx < 25:
            return None

        # Not within 3% of 52-week high
        high_52w = max(b.high for b in bars[-252:])
        if current > high_52w * 0.97:
            return None

        # Compute ATR for stop
        atr = self._compute_atr(bars)
        if atr is None or atr == 0:
            return None

        # Entry: pullback to 10-day EMA ± 0.5%
        ema10 = self._compute_ema(closes, 10)
        entry = round(ema10, 4)
        entry_low = round(entry * 0.995, 4)
        entry_high = round(entry * 1.005, 4)

        # Stop: 2x ATR below entry
        stop = round(entry - 2 * atr, 4)
        risk = entry - stop

        # Targets
        target_1 = round(entry + 1.5 * risk, 4)
        target_2 = round(entry + 2.5 * risk, 4)
        target_3 = round(high_52w, 4)  # Previous swing high

        rr = round((target_2 - entry) / risk, 2) if risk > 0 else 0

        # Sizing
        sizing = compute_sizing(
            entry, stop, market,
            settings.portfolio_value_aud,
            settings.risk_per_trade_pct,
            max_position_pct=settings.max_position_size_pct / 100,
        )

        # Overlap detection
        vas_overlap = is_top50_asx300(stock.symbol) if market == "ASX" else False
        ihvv_overlap = is_sp500_member(stock.symbol) if market != "ASX" else False

        overlap_note = None
        if vas_overlap:
            overlap_note = "You already hold indirect exposure via VAS."
        elif ihvv_overlap:
            overlap_note = "S&P 500 large-cap — overlaps with IHVV."

        return TradeIdea(
            symbol=stock.symbol,
            company_name=stock.company_name,
            market=market,
            sector=stock.gics_sector,
            is_etf=False,
            strategy_name=self.name,
            direction=Direction.LONG,
            conviction=Conviction.HIGH if momentum_score > 0.3 else Conviction.MEDIUM,
            time_horizon=TimeHorizon.POSITION,
            current_price=round(current, 4),
            suggested_entry=entry,
            entry_range_low=entry_low,
            entry_range_high=entry_high,
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
                f"12m-ex-1m return: {ret_12m*100:.1f}%",
                f"Momentum score: {momentum_score:.3f}",
                f"RSI(14): {rsi:.1f}",
                f"ADX: {adx:.1f}" if adx else "ADX: N/A",
            ],
            technical_summary=(
                f"Strong uptrend: price above 50 & 200 SMA. "
                f"RSI at {rsi:.0f}, ADX at {adx:.0f if adx else 0}. "
                f"Pullback to 10 EMA ({entry:.2f}) offers entry."
            ),
            risk_factors=[
                "Momentum reversal risk if market regime shifts",
                f"Stop at {stop:.2f} (2x ATR below entry)",
            ],
            invalidation_conditions=[
                "Price breaks below 200-day SMA",
                "RSI crosses above 80 (overbought)",
                f"ADX drops below 20 (trend weakening)",
            ],
            indicators={
                "momentum_score": round(momentum_score, 4),
                "rsi": round(rsi, 2) if rsi else None,
                "adx": round(adx, 2) if adx else None,
                "atr": round(atr, 4),
                "sma50": round(sma50, 4),
                "sma200": round(sma200, 4),
                "ema10": round(ema10, 4),
            },
            vas_overlap=vas_overlap,
            ihvv_overlap=ihvv_overlap,
            overlap_note=overlap_note,
        )

    @staticmethod
    def _compute_rsi(closes, period=14):
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    @staticmethod
    def _compute_atr(bars, period=14):
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
        return np.mean(trs) if trs else None

    @staticmethod
    def _compute_ema(closes, period):
        if len(closes) < period:
            return closes[-1]
        multiplier = 2 / (period + 1)
        ema = np.mean(closes[-period * 2:-period])  # seed with SMA
        for price in closes[-period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    @staticmethod
    def _compute_simple_adx(bars, period=14):
        from backend.strategies.regime.detector import compute_adx
        return compute_adx(bars, period)
