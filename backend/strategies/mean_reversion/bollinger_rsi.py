"""Bollinger Band + RSI Mean Reversion strategy.

Long only: identifies oversold bounces within uptrending stocks.
"""

import logging
from typing import Optional
import numpy as np

from backend.strategies.base import (
    BaseStrategy, TradeIdea, Direction, Conviction, TimeHorizon, compute_sizing,
)
from backend.data.feeds.yfinance_feed import get_daily_bars
from backend.data.universe.asx200 import is_top50_asx300
from backend.data.universe.sp500 import is_sp500_member
from backend.config import settings

logger = logging.getLogger(__name__)


class BollingerRSI(BaseStrategy):
    name = "bollinger_rsi"
    weight = 1.0

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
                logger.error("BollingerRSI error for %s: %s", stock.symbol, e)
        return ideas

    def _evaluate(self, stock, bars, market) -> Optional[TradeIdea]:
        closes = np.array([b.close for b in bars])
        volumes = np.array([b.volume for b in bars])
        current = closes[-1]

        # Bollinger Bands (20, 2 SD)
        sma20 = np.mean(closes[-20:])
        std20 = np.std(closes[-20:])
        lower_band = sma20 - 2 * std20

        if current > lower_band:
            return None  # Must be below lower band

        # RSI < 30
        rsi = self._rsi(closes)
        if rsi is None or rsi >= 30:
            return None

        # Z-score < -2.0
        z_score = (current - sma20) / std20 if std20 > 0 else 0
        if z_score > -2.0:
            return None

        # Volume capitulation: > 1.5x 10d average
        avg_vol_10 = np.mean(volumes[-10:])
        if volumes[-1] < avg_vol_10 * 1.5:
            return None

        # 200 SMA slope should be flat to positive
        if len(closes) >= 220:
            sma200_now = np.mean(closes[-200:])
            sma200_20d_ago = np.mean(closes[-220:-20])
            if sma200_now < sma200_20d_ago * 0.99:
                return None  # Declining 200 SMA

        # Quality gates
        five_day_decline = (closes[-1] / closes[-5] - 1) * 100
        if five_day_decline < -20:
            return None  # Catastrophic event

        entry = round(current, 4)
        stop = round(entry * 0.90, 4)  # 10% below entry
        target_1 = round(sma20, 4)  # Middle band
        risk = entry - stop
        rr = round((target_1 - entry) / risk, 2) if risk > 0 else 0

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
            target_2=round(sma20 + std20, 4),
            target_3=round(sma20 + 2 * std20, 4),
            risk_reward_ratio=rr,
            suggested_shares=sizing["shares"],
            position_value_aud=sizing["position_value_aud"],
            risk_amount_aud=sizing["risk_amount_aud"],
            cmc_brokerage_aud=sizing["brokerage_aud"],
            cmc_fx_cost_aud=sizing["fx_cost_aud"],
            total_trade_cost_aud=sizing["total_cost_aud"],
            small_trade_warning=sizing["small_trade_warning"],
            key_factors=[
                f"Below lower Bollinger Band ({lower_band:.2f})",
                f"RSI(14): {rsi:.1f} (oversold)",
                f"Z-score: {z_score:.2f}",
                f"Volume spike: {volumes[-1]/avg_vol_10:.1f}x average",
            ],
            technical_summary=f"Mean reversion setup: RSI {rsi:.0f}, Z-score {z_score:.1f}, volume capitulation.",
            risk_factors=["Continued selling", "10-day time limit on trade"],
            invalidation_conditions=[
                f"Price falls below {stop:.2f}",
                "10 trading days without reaching target",
            ],
            indicators={
                "rsi": round(rsi, 2),
                "z_score": round(z_score, 2),
                "lower_band": round(lower_band, 4),
                "sma20": round(sma20, 4),
                "volume_ratio": round(volumes[-1] / avg_vol_10, 2),
            },
            vas_overlap=is_top50_asx300(stock.symbol) if market == "ASX" else False,
            ihvv_overlap=is_sp500_member(stock.symbol) if market != "ASX" else False,
        )

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
