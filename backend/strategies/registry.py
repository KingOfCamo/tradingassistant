"""Strategy registry with regime gating and weights."""

import logging
from typing import Optional

from backend.strategies.base import TradeIdea
from backend.strategies.momentum.dual_momentum import DualMomentum
from backend.strategies.momentum.trend_following import TrendFollowing
from backend.strategies.momentum.breakout import Breakout
from backend.strategies.mean_reversion.bollinger_rsi import BollingerRSI
from backend.strategies.mean_reversion.pairs_scanner import PairsScanner
from backend.strategies.mean_reversion.gap_fade import GapFade
from backend.strategies.value.fundamental_screen import FundamentalScreen
from backend.strategies.value.earnings_catalyst import EarningsCatalyst
from backend.strategies.macro.sector_rotation import SectorRotation
from backend.strategies.regime.detector import (
    MarketRegime,
    is_strategy_active,
    get_current_regime,
)

logger = logging.getLogger(__name__)


STRATEGY_DEFINITIONS = {
    "dual_momentum": {
        "class": DualMomentum,
        "weight": 1.5,
        "regime_whitelist": [
            MarketRegime.STRONG_TREND_BULL,
            MarketRegime.MODERATE_TREND_BULL,
        ],
    },
    "trend_following": {
        "class": TrendFollowing,
        "weight": 1.3,
        "regime_whitelist": [
            MarketRegime.STRONG_TREND_BULL,
            MarketRegime.MODERATE_TREND_BULL,
        ],
    },
    "breakout": {
        "class": Breakout,
        "weight": 1.2,
        "regime_whitelist": [
            MarketRegime.STRONG_TREND_BULL,
            MarketRegime.MODERATE_TREND_BULL,
        ],
    },
    "bollinger_rsi": {
        "class": BollingerRSI,
        "weight": 1.0,
        "regime_whitelist": [
            MarketRegime.CHOPPY_RANGE_BOUND,
            MarketRegime.MODERATE_TREND_BULL,
        ],
    },
    "pairs_scanner": {
        "class": PairsScanner,
        "weight": 0.8,
        "regime_whitelist": [
            MarketRegime.CHOPPY_RANGE_BOUND,
            MarketRegime.MODERATE_TREND_BULL,
            MarketRegime.RISK_OFF_ELEVATED_FEAR,
        ],
    },
    "gap_fade": {
        "class": GapFade,
        "weight": 0.7,
        "regime_whitelist": [
            MarketRegime.MODERATE_TREND_BULL,
            MarketRegime.CHOPPY_RANGE_BOUND,
        ],
    },
    "fundamental_screen": {
        "class": FundamentalScreen,
        "weight": 1.4,
        "regime_whitelist": "ALL",
    },
    "earnings_catalyst": {
        "class": EarningsCatalyst,
        "weight": 1.1,
        "regime_whitelist": [
            MarketRegime.STRONG_TREND_BULL,
            MarketRegime.MODERATE_TREND_BULL,
        ],
    },
    "sector_rotation": {
        "class": SectorRotation,
        "weight": 1.2,
        "regime_whitelist": "ALL",
    },
}


def get_strategy_weight(name: str) -> float:
    return STRATEGY_DEFINITIONS.get(name, {}).get("weight", 1.0)


class StrategyRegistry:
    def get_active_strategies(self, regime: MarketRegime) -> list:
        """Return only strategies permitted in current market regime."""
        active = []
        for name, defn in STRATEGY_DEFINITIONS.items():
            whitelist = defn["regime_whitelist"]
            if whitelist == "ALL" or regime in whitelist:
                active.append(defn)
        return active

    async def run_all(self, universe: list, market: str) -> list[TradeIdea]:
        """Run all regime-appropriate strategies and return combined ideas."""
        # Cap universe on free-tier data plans to avoid burning through
        # per-minute credit limits. Raise scan_max_symbols via env when
        # you upgrade Twelve Data.
        from backend.config import settings
        if settings.scan_max_symbols and len(universe) > settings.scan_max_symbols:
            logger.info(
                "Capping scan universe to %d symbols (was %d) for %s",
                settings.scan_max_symbols, len(universe), market,
            )
            universe = universe[:settings.scan_max_symbols]

        regime = await get_current_regime(market)
        active = self.get_active_strategies(regime)
        all_ideas = []

        for strategy_def in active:
            try:
                strategy = strategy_def["class"]()
                ideas = await strategy.generate_signals(universe, market)

                # Tag each idea with regime info
                for idea in ideas:
                    idea.regime_at_creation = regime.value
                    idea.regime_compatible = True

                all_ideas.extend(ideas)
                logger.info(
                    "Strategy %s generated %d ideas in %s regime",
                    strategy.name, len(ideas), regime.value,
                )
            except Exception as e:
                logger.error(
                    "Strategy %s failed: %s",
                    strategy_def["class"].__name__, e,
                )

        return all_ideas
