"""Idea aging, re-evaluation, and automatic invalidation.

Every trade idea has a lifecycle. The system re-evaluates all active ideas
every morning before generating new ones.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.strategies.base import TradeIdea, IdeaStatus
from backend.config import settings

logger = logging.getLogger(__name__)


def evaluate_idea_lifecycle(
    idea: TradeIdea,
    current_price: float,
    current_regime: str,
) -> TradeIdea:
    """
    Re-evaluate a single idea against current conditions.
    Updates status and returns the modified idea.
    """
    now = datetime.now(timezone.utc)
    idea.last_evaluated_at = now

    # Only evaluate ACTIVE or WATCHING ideas
    if idea.status not in (IdeaStatus.ACTIVE, IdeaStatus.WATCHING):
        return idea

    # 1. ENTRY RANGE CHECK
    entry_miss_pct = settings.idea_entry_miss_pct / 100
    if idea.direction.value == "long":
        if current_price > idea.entry_range_high * (1 + entry_miss_pct):
            idea.status = IdeaStatus.ENTRY_MISSED
            idea.status_reason = (
                f"Price ran above entry range — "
                f"current {current_price:.2f} vs entry high {idea.entry_range_high:.2f}"
            )
            return idea

        if current_price < idea.stop_loss:
            idea.status = IdeaStatus.INVALIDATED
            idea.status_reason = "Price hit stop level before entry — thesis invalidated."
            return idea
    else:
        if current_price < idea.entry_range_low * (1 - entry_miss_pct):
            idea.status = IdeaStatus.ENTRY_MISSED
            idea.status_reason = "Price moved below entry range for short."
            return idea

    # 2. MAX ADVERSE EXCURSION — urgent escalation
    if idea.current_price > 0 and idea.stop_loss > 0:
        if idea.direction.value == "long":
            risk = idea.suggested_entry - idea.stop_loss
            adverse = idea.suggested_entry - current_price
        else:
            risk = idea.stop_loss - idea.suggested_entry
            adverse = current_price - idea.suggested_entry

        if risk > 0 and adverse > 2 * risk:
            idea.key_factors.append(
                "URGENT: Position exceeds 2x original risk. Review immediately."
            )

    # 3. AGE CHECK
    max_age = settings.idea_max_age_days
    # Tier 3+ confluence ideas get double max age
    if idea.confluence_tier >= 3:
        max_age *= 2

    age = (now - idea.created_at).days
    if age > max_age:
        idea.status = IdeaStatus.EXPIRED
        idea.status_reason = f"Idea older than {max_age} days without being acted on."
        return idea

    # 4. REGIME COMPATIBILITY CHECK
    if idea.regime_at_creation and idea.regime_at_creation != current_regime:
        idea.regime_compatible = False
        # Don't auto-invalidate — regime can shift back
        if "Regime changed" not in str(idea.key_factors):
            idea.key_factors.append(
                f"Regime changed: {idea.regime_at_creation} → {current_regime} — lower confidence"
            )

    # 5. Update current price
    idea.current_price = current_price

    return idea


def evaluate_all_ideas(
    ideas: list[TradeIdea],
    current_prices: dict[str, float],
    current_regime: str,
) -> tuple[list[TradeIdea], list[TradeIdea]]:
    """
    Re-evaluate all active ideas.
    Returns (active_ideas, archived_ideas).
    """
    active = []
    archived = []

    for idea in ideas:
        price = current_prices.get(idea.symbol, idea.current_price)
        evaluated = evaluate_idea_lifecycle(idea, price, current_regime)

        if evaluated.status in (
            IdeaStatus.ACTIVE,
            IdeaStatus.WATCHING,
        ):
            active.append(evaluated)
        else:
            archived.append(evaluated)
            logger.info(
                "Idea %s (%s) archived: %s — %s",
                idea.symbol,
                idea.strategy_name,
                idea.status.value,
                idea.status_reason,
            )

    return active, archived


def check_confluence_strengthening(
    idea: TradeIdea,
    new_confluence_score: float,
) -> TradeIdea:
    """Check if confluence has increased since idea was generated."""
    if new_confluence_score > idea.confluence_score:
        idea.confluence_score = new_confluence_score
        idea.key_factors.append(
            f"Thesis strengthening: confluence score increased to {new_confluence_score:.1f}"
        )
    return idea
