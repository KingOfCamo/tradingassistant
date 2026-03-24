"""Portfolio heat map: beta, sector concentration, correlation tracking."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PositionRisk:
    symbol: str
    market: str
    sector: str
    is_etf: bool
    shares: int
    entry_price: float
    current_price: float
    current_value_aud: float
    weight_pct: float
    beta: float
    pnl_pct: float
    stop_distance_pct: Optional[float] = None


@dataclass
class PortfolioHeatMap:
    total_value_aud: float
    cash_pct: float
    portfolio_beta: float
    avg_pairwise_correlation: float
    sector_weights: dict  # {sector: pct}
    position_risks: list[PositionRisk]
    warnings: list[str]
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def compute_portfolio_beta(positions: list[PositionRisk]) -> float:
    """Weighted portfolio beta."""
    if not positions:
        return 0.0
    total_weight = sum(p.weight_pct for p in positions)
    if total_weight == 0:
        return 0.0
    return sum(p.weight_pct * p.beta for p in positions) / total_weight


def compute_sector_weights(positions: list[PositionRisk]) -> dict:
    """Compute sector concentration."""
    sectors = {}
    for p in positions:
        sectors[p.sector] = sectors.get(p.sector, 0) + p.weight_pct
    return {k: round(v, 2) for k, v in sorted(sectors.items(), key=lambda x: -x[1])}


def compute_warnings(
    sector_weights: dict,
    portfolio_beta: float,
    avg_correlation: float,
    cash_pct: float,
) -> list[str]:
    """Generate risk warnings based on portfolio state."""
    warnings = []

    # Sector concentration
    max_sector_pct = settings.max_sector_concentration_pct
    for sector, weight in sector_weights.items():
        if weight > max_sector_pct:
            warnings.append(
                f"{sector} now {weight:.1f}% of portfolio — above {max_sector_pct:.0f}% threshold."
            )

    # Portfolio beta
    if portfolio_beta > settings.max_portfolio_beta:
        warnings.append(
            f"Portfolio beta is {portfolio_beta:.2f} — high market sensitivity "
            f"(threshold: {settings.max_portfolio_beta:.1f})."
        )

    # Poor diversification
    if avg_correlation > settings.correlation_warning_threshold:
        warnings.append(
            f"Positions are highly correlated ({avg_correlation:.2f}) — low diversification."
        )

    # Cash depleted
    if cash_pct < 0.10:
        warnings.append(
            f"Less than {cash_pct * 100:.0f}% cash — limited capacity for new positions."
        )

    return warnings


def simulate_position_impact(
    current_heat: PortfolioHeatMap,
    new_symbol: str,
    new_sector: str,
    new_value_aud: float,
    new_beta: float,
) -> dict:
    """Simulate adding a new position to see portfolio impact."""
    new_total = current_heat.total_value_aud + new_value_aud
    new_weight = (new_value_aud / new_total * 100) if new_total > 0 else 0

    # Sector impact
    new_sector_weights = dict(current_heat.sector_weights)
    # Recompute all weights with new total
    for sector in new_sector_weights:
        old_value = current_heat.total_value_aud * new_sector_weights[sector] / 100
        new_sector_weights[sector] = round(old_value / new_total * 100, 2)

    old_sector_weight = new_sector_weights.get(new_sector, 0)
    new_sector_weight = old_sector_weight + new_weight
    new_sector_weights[new_sector] = round(new_sector_weight, 2)

    # Beta impact
    old_beta = current_heat.portfolio_beta
    # Approximate: weighted average including new position
    total_invested_pct = 100 - current_heat.cash_pct * 100
    new_invested = total_invested_pct + new_weight
    new_portfolio_beta = (
        (old_beta * total_invested_pct + new_beta * new_weight) / new_invested
        if new_invested > 0 else old_beta
    )

    return {
        "symbol": new_symbol,
        "sector": new_sector,
        "position_weight_pct": round(new_weight, 2),
        "sector_delta": f"{new_sector}: {old_sector_weight:.1f}% → {new_sector_weight:.1f}%",
        "beta_delta": round(new_portfolio_beta - old_beta, 3),
        "new_portfolio_beta": round(new_portfolio_beta, 3),
        "sector_warning": new_sector_weight > settings.max_sector_concentration_pct,
        "beta_warning": new_portfolio_beta > settings.max_portfolio_beta,
    }


async def compute_heat_map(
    positions: list[dict],
    portfolio_value_aud: float = None,
) -> PortfolioHeatMap:
    """
    Compute full portfolio heat map from position data.

    positions: list of dicts with keys:
        symbol, market, sector, is_etf, shares, entry_price,
        current_price, beta, stop_loss (optional)
    """
    if portfolio_value_aud is None:
        portfolio_value_aud = settings.portfolio_value_aud

    # Convert position dicts to PositionRisk objects
    position_risks = []
    total_invested = 0

    for p in positions:
        current_value = p["shares"] * p["current_price"]
        # Convert US positions to AUD if needed
        if p["market"] != "ASX":
            fx_rate = 0.65  # Approximate — would use live rate
            current_value = current_value / fx_rate

        weight = (current_value / portfolio_value_aud * 100) if portfolio_value_aud > 0 else 0
        pnl_pct = ((p["current_price"] - p["entry_price"]) / p["entry_price"] * 100) if p["entry_price"] > 0 else 0

        stop_distance = None
        if p.get("stop_loss") and p["current_price"] > 0:
            stop_distance = ((p["current_price"] - p["stop_loss"]) / p["current_price"] * 100)

        pr = PositionRisk(
            symbol=p["symbol"],
            market=p["market"],
            sector=p.get("sector", "Unknown"),
            is_etf=p.get("is_etf", False),
            shares=p["shares"],
            entry_price=p["entry_price"],
            current_price=p["current_price"],
            current_value_aud=round(current_value, 2),
            weight_pct=round(weight, 2),
            beta=p.get("beta", 1.0),
            pnl_pct=round(pnl_pct, 2),
            stop_distance_pct=round(stop_distance, 2) if stop_distance else None,
        )
        position_risks.append(pr)
        total_invested += current_value

    cash_pct = max(0, (portfolio_value_aud - total_invested) / portfolio_value_aud) if portfolio_value_aud > 0 else 1.0

    portfolio_beta = compute_portfolio_beta(position_risks)
    sector_weights = compute_sector_weights(position_risks)

    # Correlation placeholder (would compute from historical returns)
    avg_correlation = 0.4

    warnings = compute_warnings(sector_weights, portfolio_beta, avg_correlation, cash_pct)

    return PortfolioHeatMap(
        total_value_aud=round(portfolio_value_aud, 2),
        cash_pct=round(cash_pct, 3),
        portfolio_beta=round(portfolio_beta, 3),
        avg_pairwise_correlation=avg_correlation,
        sector_weights=sector_weights,
        position_risks=position_risks,
        warnings=warnings,
    )
