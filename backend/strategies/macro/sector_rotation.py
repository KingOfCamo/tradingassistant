"""Macro Sector Rotation strategy.

Weekly sector scoring and economic cycle mapping.
"""

import logging
from dataclasses import dataclass
from typing import Optional
import numpy as np

from backend.strategies.base import (
    BaseStrategy, TradeIdea, Direction, Conviction, TimeHorizon, compute_sizing,
)
from backend.data.feeds.yfinance_feed import get_daily_bars
from backend.config import settings

logger = logging.getLogger(__name__)

# ASX Sector ETFs
SECTOR_ETFS = {
    "Materials": "XMJ",
    "Financials": "XFJ",
    "Energy": "XEJ",
    "Health Care": "XHJ",
    "Industrials": "XIJ",
    "Consumer Discretionary": "XDJ",
    "Consumer Staples": "XSJ",
    "Real Estate": "XPJ",
    "Utilities": "XUJ",
}

# Economic cycle sector preferences
CYCLE_SECTORS = {
    "early_recovery": ["Financials", "Consumer Discretionary", "Industrials"],
    "mid_expansion": ["Information Technology", "Communication Services", "Materials"],
    "late_cycle": ["Energy", "Consumer Staples", "Health Care"],
    "contraction": ["Utilities", "Health Care", "Consumer Staples"],
}


@dataclass
class SectorScore:
    sector: str
    etf_symbol: str
    score: float
    ret_1m: float
    ret_3m: float
    ret_6m: float
    above_200sma: bool
    above_50sma: bool
    ranking: int = 0


class SectorRotation(BaseStrategy):
    name = "sector_rotation"
    weight = 1.2

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
        if market != "ASX":
            return []  # Focus on ASX sector ETFs for now

        ideas = []
        scores = await self._score_sectors()

        # Generate ideas for top-scoring sectors (score > 75/100)
        for score in scores:
            if score.score > 75:
                try:
                    idea = await self._create_sector_idea(score, market)
                    if idea:
                        ideas.append(idea)
                except Exception as e:
                    logger.error("SectorRotation error for %s: %s", score.sector, e)

        return ideas

    async def _score_sectors(self) -> list[SectorScore]:
        scores = []

        for sector, etf_sym in SECTOR_ETFS.items():
            try:
                bars = await get_daily_bars(etf_sym, "ASX", period="1y")
                if len(bars) < 130:
                    continue

                closes = np.array([b.close for b in bars])
                current = closes[-1]

                ret_1m = (current / closes[-22] - 1) * 100 if len(closes) > 22 else 0
                ret_3m = (current / closes[-63] - 1) * 100 if len(closes) > 63 else 0
                ret_6m = (current / closes[-126] - 1) * 100 if len(closes) > 126 else 0

                sma200 = np.mean(closes[-200:]) if len(closes) >= 200 else np.mean(closes)
                sma50 = np.mean(closes[-50:]) if len(closes) >= 50 else np.mean(closes)

                # Composite score (weighted)
                score = (
                    ret_1m * 0.15 +
                    ret_3m * 0.25 +
                    ret_6m * 0.30 +
                    (10 if current > sma200 else -10) * 0.15 +
                    (10 if current > sma50 else -10) * 0.10 +
                    min(ret_6m - ret_3m, 10) * 0.05  # Alpha component
                )

                # Normalize to 0-100
                score = max(0, min(100, 50 + score))

                scores.append(SectorScore(
                    sector=sector,
                    etf_symbol=etf_sym,
                    score=round(score, 1),
                    ret_1m=round(ret_1m, 2),
                    ret_3m=round(ret_3m, 2),
                    ret_6m=round(ret_6m, 2),
                    above_200sma=current > sma200,
                    above_50sma=current > sma50,
                ))

            except Exception as e:
                logger.error("Sector scoring error for %s: %s", sector, e)

        # Rank
        scores.sort(key=lambda x: x.score, reverse=True)
        for i, s in enumerate(scores):
            s.ranking = i + 1

        return scores

    async def _create_sector_idea(self, score: SectorScore, market: str) -> Optional[TradeIdea]:
        bars = await get_daily_bars(score.etf_symbol, market, period="3mo")
        if not bars:
            return None

        current = bars[-1].close
        entry = round(current, 4)
        stop = round(entry * 0.95, 4)
        risk = entry - stop

        sizing = compute_sizing(
            entry, stop, market,
            settings.portfolio_value_aud, settings.risk_per_trade_pct,
        )

        return TradeIdea(
            symbol=score.etf_symbol,
            company_name=f"{score.sector} Sector ETF",
            market=market,
            sector=score.sector,
            is_etf=True,
            strategy_name=self.name,
            direction=Direction.LONG,
            conviction=Conviction.MEDIUM,
            time_horizon=TimeHorizon.POSITION,
            current_price=current,
            suggested_entry=entry,
            entry_range_low=round(entry * 0.99, 4),
            entry_range_high=round(entry * 1.01, 4),
            stop_loss=stop,
            target_1=round(entry * 1.05, 4),
            target_2=round(entry * 1.10, 4),
            target_3=round(entry * 1.15, 4),
            risk_reward_ratio=round(0.10 * entry / risk, 2) if risk > 0 else 0,
            suggested_shares=sizing["shares"],
            position_value_aud=sizing["position_value_aud"],
            risk_amount_aud=sizing["risk_amount_aud"],
            cmc_brokerage_aud=sizing["brokerage_aud"],
            cmc_fx_cost_aud=sizing["fx_cost_aud"],
            total_trade_cost_aud=sizing["total_cost_aud"],
            small_trade_warning=sizing["small_trade_warning"],
            key_factors=[
                f"Sector rank: #{score.ranking}",
                f"Composite score: {score.score}/100",
                f"6m return: {score.ret_6m:+.1f}%",
            ],
            technical_summary=(
                f"{score.sector} sector scoring {score.score}/100. "
                f"Returns: 1m {score.ret_1m:+.1f}%, 3m {score.ret_3m:+.1f}%, 6m {score.ret_6m:+.1f}%."
            ),
            risk_factors=["Sector rotation can reverse quickly"],
            invalidation_conditions=["Sector drops below rank #5", "Score falls below 50"],
            indicators={
                "sector_score": score.score,
                "ranking": score.ranking,
                "ret_1m": score.ret_1m,
                "ret_3m": score.ret_3m,
                "ret_6m": score.ret_6m,
            },
        )
