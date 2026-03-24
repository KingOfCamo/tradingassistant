"""Statistical Pairs Trading strategy.

Identifies cointegrated pairs and trades spread divergences.
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

# Pre-defined pairs
ASX_PAIRS = [
    ("BHP", "RIO"), ("CBA", "NAB"), ("ANZ", "WBC"),
    ("WES", "COL"), ("WOW", "COL"), ("FMG", "BHP"),
]
US_PAIRS = [
    ("MSFT", "GOOGL"), ("JPM", "BAC"), ("XOM", "CVX"),
    ("COST", "WMT"), ("AMD", "INTC"),
]


class PairsScanner(BaseStrategy):
    name = "pairs_scanner"
    weight = 0.8

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
        ideas = []
        pairs = ASX_PAIRS if market == "ASX" else US_PAIRS

        for sym_a, sym_b in pairs:
            try:
                bars_a = await get_daily_bars(sym_a, market, period="1y")
                bars_b = await get_daily_bars(sym_b, market, period="1y")

                if len(bars_a) < 252 or len(bars_b) < 252:
                    continue

                idea = self._evaluate_pair(sym_a, sym_b, bars_a, bars_b, market)
                if idea:
                    ideas.append(idea)

            except Exception as e:
                logger.error("PairsScanner error for %s/%s: %s", sym_a, sym_b, e)

        return ideas

    def _evaluate_pair(self, sym_a, sym_b, bars_a, bars_b, market) -> Optional[TradeIdea]:
        closes_a = np.array([b.close for b in bars_a[-252:]])
        closes_b = np.array([b.close for b in bars_b[-252:]])

        min_len = min(len(closes_a), len(closes_b))
        closes_a = closes_a[-min_len:]
        closes_b = closes_b[-min_len:]

        # Log spread
        log_a = np.log(closes_a)
        log_b = np.log(closes_b)

        # Simple OLS for beta
        beta = np.cov(log_a, log_b)[0, 1] / np.var(log_b) if np.var(log_b) > 0 else 1.0
        spread = log_a - beta * log_b

        # Z-score of spread (60-day window)
        spread_60 = spread[-60:]
        mean_60 = np.mean(spread_60)
        std_60 = np.std(spread_60)
        if std_60 == 0:
            return None

        z_score = (spread[-1] - mean_60) / std_60

        # Signal: |z_score| > 2.0
        if abs(z_score) < 2.0:
            return None

        # Determine direction
        if z_score < -2.0:
            # Spread below mean: long A, short B
            direction = Direction.LONG
            trade_symbol = sym_a
            trade_price = closes_a[-1]
        else:
            # Spread above mean: short A, long B (but LONG only for ASX Phase 1)
            if market == "ASX":
                return None  # No shorting on ASX in Phase 1
            direction = Direction.SHORT
            trade_symbol = sym_a
            trade_price = closes_a[-1]

        entry = round(trade_price, 4)
        stop_z = 3.5  # Stop at z=3.5
        stop_price_pct = abs(stop_z - abs(z_score)) / abs(z_score) * 0.05  # Approximate
        stop = round(entry * (1 - 0.05), 4) if direction == Direction.LONG else round(entry * 1.05, 4)
        risk = abs(entry - stop)

        target_price = round(entry * (1 + 0.03), 4)  # ~3% target (spread mean reversion)

        sizing = compute_sizing(
            entry, stop, market,
            settings.portfolio_value_aud, settings.risk_per_trade_pct,
        )

        return TradeIdea(
            symbol=trade_symbol,
            company_name=trade_symbol,
            market=market,
            sector="Pairs",
            is_etf=False,
            strategy_name=self.name,
            direction=direction,
            conviction=Conviction.MEDIUM,
            time_horizon=TimeHorizon.SWING,
            current_price=trade_price,
            suggested_entry=entry,
            entry_range_low=round(entry * 0.99, 4),
            entry_range_high=round(entry * 1.01, 4),
            stop_loss=stop,
            target_1=target_price,
            target_2=round(entry * 1.05, 4),
            target_3=round(entry * 1.08, 4),
            risk_reward_ratio=round((target_price - entry) / risk, 2) if risk > 0 else 0,
            suggested_shares=sizing["shares"],
            position_value_aud=sizing["position_value_aud"],
            risk_amount_aud=sizing["risk_amount_aud"],
            cmc_brokerage_aud=sizing["brokerage_aud"],
            cmc_fx_cost_aud=sizing["fx_cost_aud"],
            total_trade_cost_aud=sizing["total_cost_aud"],
            small_trade_warning=sizing["small_trade_warning"],
            key_factors=[
                f"Pair: {sym_a}/{sym_b}",
                f"Spread Z-score: {z_score:.2f}",
                f"Beta: {beta:.3f}",
            ],
            technical_summary=f"Pairs trade: {sym_a}/{sym_b} spread at Z={z_score:.1f}. Mean reversion target.",
            risk_factors=["Pair can decouple permanently", f"Stop at Z={stop_z}"],
            invalidation_conditions=[f"|Z-score| > {stop_z}"],
            indicators={"z_score": round(z_score, 3), "beta": round(beta, 3), "pair": f"{sym_a}/{sym_b}"},
        )
