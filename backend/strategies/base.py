"""Strategy base: TradeIdea dataclass and position sizing."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class Conviction(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TimeHorizon(str, Enum):
    INTRADAY = "intraday"
    SWING = "swing"
    POSITION = "position"
    INVESTMENT = "investment"


class IdeaStatus(str, Enum):
    ACTIVE = "active"
    WATCHING = "watching"
    INVALIDATED = "invalidated"
    ENTRY_MISSED = "entry_missed"
    EXPIRED = "expired"
    ARCHIVED = "archived"
    ACTED = "acted"


@dataclass
class TradeIdea:
    symbol: str
    company_name: str
    market: str
    sector: str
    is_etf: bool
    strategy_name: str
    direction: Direction
    conviction: Conviction
    time_horizon: TimeHorizon
    status: IdeaStatus = IdeaStatus.ACTIVE

    current_price: float = 0.0
    suggested_entry: float = 0.0
    entry_range_low: float = 0.0
    entry_range_high: float = 0.0
    stop_loss: float = 0.0
    target_1: float = 0.0
    target_2: float = 0.0
    target_3: float = 0.0
    risk_reward_ratio: float = 0.0

    suggested_shares: int = 0
    position_value_aud: float = 0.0
    risk_amount_aud: float = 0.0
    cmc_brokerage_aud: float = 0.0
    cmc_fx_cost_aud: float = 0.0
    total_trade_cost_aud: float = 0.0
    small_trade_warning: Optional[str] = None

    key_factors: list = field(default_factory=list)
    technical_summary: str = ""
    fundamental_context: str = ""
    risk_factors: list = field(default_factory=list)
    invalidation_conditions: list = field(default_factory=list)
    indicators: dict = field(default_factory=dict)
    chart_patterns: list = field(default_factory=list)

    vas_overlap: bool = False
    ihvv_overlap: bool = False
    overlap_note: Optional[str] = None

    portfolio_sector_delta: Optional[str] = None
    portfolio_beta_delta: Optional[float] = None
    portfolio_concentration_warning: Optional[str] = None

    regime_at_creation: str = ""
    regime_compatible: bool = True

    confluence_score: float = 0.0
    confluence_tier: int = 0

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_evaluated_at: Optional[datetime] = None
    status_reason: Optional[str] = None

    ai_analysis: Optional[dict] = None
    ai_verdict: Optional[str] = None
    ai_conviction_override: Optional[Conviction] = None

    user_action: Optional[str] = None
    user_pass_reason: Optional[str] = None
    user_notes: Optional[str] = None


def compute_sizing(
    entry: float,
    stop: float,
    market: str,
    portfolio_value_aud: float,
    risk_pct: float,
    aud_usd_rate: float = 0.65,
    cmc_fx_spread_pct: float = 0.0065,
    max_position_pct: float = 0.10,
    regime: str = "",
) -> dict:
    """Compute position size, brokerage, and cost breakdown."""
    risk_per_trade_aud = portfolio_value_aud * (risk_pct / 100)

    # Regime haircut: reduce risk in elevated/crisis regimes
    if regime in ("RISK_OFF_ELEVATED_FEAR", "CRISIS_EXTREME_FEAR"):
        risk_per_trade_aud *= 0.5

    risk_per_share_local = abs(entry - stop)
    if risk_per_share_local == 0:
        return _empty_sizing()

    if market == "ASX":
        shares = int(risk_per_trade_aud / risk_per_share_local)
        position_value_aud = shares * entry
        brokerage = 0.0 if position_value_aud >= 1000 else 9.90
        fx_cost = 0.0
    else:
        effective_rate = aud_usd_rate * (1 - cmc_fx_spread_pct)
        if effective_rate == 0:
            return _empty_sizing()
        risk_per_share_aud = risk_per_share_local / effective_rate
        shares = int(risk_per_trade_aud / risk_per_share_aud)
        position_value_aud = (shares * entry) / effective_rate
        brokerage = 0.0
        fx_cost = position_value_aud * cmc_fx_spread_pct * 2

    # Cap at max position size
    max_aud = portfolio_value_aud * max_position_pct
    if position_value_aud > max_aud:
        if market == "ASX":
            shares = int(max_aud / entry) if entry > 0 else 0
            position_value_aud = shares * entry
        else:
            shares = int(max_aud * effective_rate / entry) if entry > 0 else 0
            position_value_aud = max_aud

    total_cost = brokerage + fx_cost
    breakeven_pct = (total_cost / position_value_aud * 100) if position_value_aud > 0 else 0

    warning = None
    if market == "ASX" and position_value_aud < 500:
        warning = (
            f"$9.90 on a ${position_value_aud:.0f} position = "
            f"{breakeven_pct:.1f}% cost. Consider waiting to place "
            f"a single trade above $1,000 for $0 brokerage."
        )
    elif market == "ASX" and position_value_aud < 1000:
        warning = (
            f"Under $1,000 threshold — $9.90 brokerage applies "
            f"({breakeven_pct:.1f}% of position)."
        )

    return {
        "shares": shares,
        "position_value_aud": round(position_value_aud, 2),
        "risk_amount_aud": round(risk_per_trade_aud, 2),
        "brokerage_aud": round(brokerage, 2),
        "fx_cost_aud": round(fx_cost, 2),
        "total_cost_aud": round(total_cost, 2),
        "breakeven_pct": round(breakeven_pct, 3),
        "small_trade_warning": warning,
    }


def _empty_sizing():
    return {
        "shares": 0,
        "position_value_aud": 0,
        "risk_amount_aud": 0,
        "brokerage_aud": 0,
        "fx_cost_aud": 0,
        "total_cost_aud": 0,
        "breakeven_pct": 0,
        "small_trade_warning": None,
    }


class BaseStrategy:
    """Base class for all strategies."""
    name: str = "base"
    weight: float = 1.0

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
        raise NotImplementedError
