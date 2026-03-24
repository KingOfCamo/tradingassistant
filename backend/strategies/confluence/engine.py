"""Signal Confluence Engine.

Takes independent strategy outputs and identifies when multiple
methodologies agree on the same trade.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from backend.strategies.base import TradeIdea, Direction
from backend.strategies.registry import get_strategy_weight

logger = logging.getLogger(__name__)


@dataclass
class ConfluenceAlert:
    symbol: str
    company_name: str
    market: str
    direction: Direction
    confluence_score: float
    tier: int  # 1-4
    agreeing_strategies: list[str]
    strategy_ideas: list[TradeIdea]
    consensus_entry: float
    consensus_stop: float
    consensus_target: float
    consensus_rr: float
    regime: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ai_analysis: Optional[dict] = None


def compute_confluence_score(ideas: list[TradeIdea]) -> float:
    """Sum of weighted strategy votes for agreeing ideas."""
    return sum(get_strategy_weight(idea.strategy_name) for idea in ideas)


def determine_tier(score: float) -> int:
    """
    TIER 1 — WATCH (1.5-2.4): 2 strategies agreeing
    TIER 2 — NOTABLE (2.5-3.4): 2-3 strategies with strong weights
    TIER 3 — HIGH CONVICTION (3.5-4.9): 3+ strategies
    TIER 4 — RARE SIGNAL (>= 5.0): 4+ strategies
    """
    if score >= 5.0:
        return 4
    elif score >= 3.5:
        return 3
    elif score >= 2.5:
        return 2
    elif score >= 1.5:
        return 1
    return 0


def compute_consensus_levels(ideas: list[TradeIdea]) -> dict:
    """Weighted average of strategy entry/stop/target levels."""
    if not ideas:
        return {"entry": 0, "stop": 0, "target": 0, "rr": 0}

    total_weight = sum(get_strategy_weight(i.strategy_name) for i in ideas)
    if total_weight == 0:
        total_weight = 1

    entry = sum(
        i.suggested_entry * get_strategy_weight(i.strategy_name)
        for i in ideas
    ) / total_weight

    # Most conservative stop (farthest from entry for longs)
    if ideas[0].direction == Direction.LONG:
        stop = min(i.stop_loss for i in ideas)
    else:
        stop = max(i.stop_loss for i in ideas)

    target = sum(
        i.target_2 * get_strategy_weight(i.strategy_name)
        for i in ideas
    ) / total_weight

    risk = abs(entry - stop)
    rr = round(abs(target - entry) / risk, 2) if risk > 0 else 0

    return {
        "entry": round(entry, 4),
        "stop": round(stop, 4),
        "target": round(target, 4),
        "rr": rr,
    }


def evaluate(all_ideas: list[TradeIdea], min_strategies: int = 2) -> list[ConfluenceAlert]:
    """
    Evaluate all strategy outputs for confluence.
    Groups ideas by (symbol, direction), scores them, and creates alerts.
    """
    # Group ideas by symbol + direction
    groups: dict[tuple, list[TradeIdea]] = {}
    for idea in all_ideas:
        key = (idea.symbol, idea.direction)
        if key not in groups:
            groups[key] = []
        groups[key].append(idea)

    alerts = []
    for (symbol, direction), ideas in groups.items():
        # Deduplicate by strategy name
        seen_strategies = set()
        unique_ideas = []
        for idea in ideas:
            if idea.strategy_name not in seen_strategies:
                seen_strategies.add(idea.strategy_name)
                unique_ideas.append(idea)

        if len(unique_ideas) < min_strategies:
            continue

        score = compute_confluence_score(unique_ideas)
        tier = determine_tier(score)

        if tier == 0:
            continue

        consensus = compute_consensus_levels(unique_ideas)

        alert = ConfluenceAlert(
            symbol=symbol,
            company_name=unique_ideas[0].company_name,
            market=unique_ideas[0].market,
            direction=direction,
            confluence_score=round(score, 2),
            tier=tier,
            agreeing_strategies=[i.strategy_name for i in unique_ideas],
            strategy_ideas=unique_ideas,
            consensus_entry=consensus["entry"],
            consensus_stop=consensus["stop"],
            consensus_target=consensus["target"],
            consensus_rr=consensus["rr"],
            regime=unique_ideas[0].regime_at_creation,
        )
        alerts.append(alert)

    # Sort by score descending
    alerts.sort(key=lambda a: a.confluence_score, reverse=True)

    # Also detect conflicting signals
    _tag_conflicts(all_ideas)

    return alerts


def _tag_conflicts(all_ideas: list[TradeIdea]) -> None:
    """Tag ideas where strategies disagree on direction."""
    by_symbol: dict[str, dict] = {}
    for idea in all_ideas:
        if idea.symbol not in by_symbol:
            by_symbol[idea.symbol] = {"long": [], "short": []}
        by_symbol[idea.symbol][idea.direction.value].append(idea.strategy_name)

    for symbol, directions in by_symbol.items():
        if directions["long"] and directions["short"]:
            # Conflicting signals — tag all ideas for this symbol
            for idea in all_ideas:
                if idea.symbol == symbol:
                    idea.key_factors.append(
                        f"CONFLICTED: {', '.join(directions['long'])} say LONG, "
                        f"{', '.join(directions['short'])} say SHORT"
                    )
