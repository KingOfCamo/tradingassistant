"""SQLAlchemy database models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    ForeignKey,
    Date,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from backend.db.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)


class AuthAuditLog(Base):
    __tablename__ = "auth_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    path = Column(String(255), nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TradeIdeaModel(Base):
    __tablename__ = "trade_ideas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200))
    market = Column(String(10), nullable=False)
    sector = Column(String(100))
    is_etf = Column(Boolean, default=False)
    strategy_name = Column(String(50), nullable=False)
    direction = Column(String(10), nullable=False)
    conviction = Column(String(10), nullable=False)
    time_horizon = Column(String(20))
    status = Column(String(20), default="active", index=True)
    status_reason = Column(Text)

    current_price = Column(Numeric(12, 4))
    suggested_entry = Column(Numeric(12, 4))
    entry_range_low = Column(Numeric(12, 4))
    entry_range_high = Column(Numeric(12, 4))
    stop_loss = Column(Numeric(12, 4))
    target_1 = Column(Numeric(12, 4))
    target_2 = Column(Numeric(12, 4))
    target_3 = Column(Numeric(12, 4))
    risk_reward_ratio = Column(Numeric(6, 2))

    suggested_shares = Column(Integer)
    position_value_aud = Column(Numeric(12, 2))
    risk_amount_aud = Column(Numeric(12, 2))
    cmc_brokerage_aud = Column(Numeric(8, 2))
    cmc_fx_cost_aud = Column(Numeric(8, 2))
    total_trade_cost_aud = Column(Numeric(8, 2))
    small_trade_warning = Column(Text)

    key_factors = Column(JSONB)
    technical_summary = Column(Text)
    fundamental_context = Column(Text)
    risk_factors = Column(JSONB)
    invalidation_conditions = Column(JSONB)
    indicators = Column(JSONB)
    chart_patterns = Column(JSONB)

    vas_overlap = Column(Boolean, default=False)
    ihvv_overlap = Column(Boolean, default=False)
    overlap_note = Column(Text)

    portfolio_sector_delta = Column(Text)
    portfolio_beta_delta = Column(Numeric(6, 3))

    regime_at_creation = Column(String(40))
    regime_compatible = Column(Boolean, default=True)
    confluence_score = Column(Numeric(6, 2), default=0)
    confluence_tier = Column(Integer, default=0)

    ai_analysis = Column(JSONB)
    ai_verdict = Column(String(30))
    ai_conviction_override = Column(String(10))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    data_as_of = Column(DateTime(timezone=True))
    last_evaluated_at = Column(DateTime(timezone=True))

    user_action = Column(String(20))
    user_pass_reason = Column(String(100))
    user_action_at = Column(DateTime(timezone=True))
    user_notes = Column(Text)


class ConfluenceAlertModel(Base):
    __tablename__ = "confluence_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200))
    market = Column(String(10), nullable=False)
    direction = Column(String(10))
    confluence_score = Column(Numeric(6, 2))
    tier = Column(Integer)
    agreeing_strategies = Column(JSONB)
    consensus_entry = Column(Numeric(12, 4))
    consensus_stop = Column(Numeric(12, 4))
    consensus_target = Column(Numeric(12, 4))
    consensus_rr = Column(Numeric(6, 2))
    regime = Column(String(40))
    ai_analysis = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated_at = Column(DateTime(timezone=True))
    status = Column(String(20), default="active")
    user_action = Column(String(20))
    user_action_at = Column(DateTime(timezone=True))


class MarketRegimeLog(Base):
    __tablename__ = "market_regime_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market = Column(String(10), nullable=False)
    regime = Column(String(40), nullable=False)
    vix = Column(Numeric(8, 2))
    index_adx = Column(Numeric(8, 2))
    breadth_pct = Column(Numeric(6, 3))
    yield_spread = Column(Numeric(8, 4))
    ad_ratio = Column(Numeric(8, 3))
    strategies_active = Column(JSONB)
    strategies_suppressed = Column(JSONB)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class PortfolioHeatSnapshot(Base):
    __tablename__ = "portfolio_heat_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    total_value_aud = Column(Numeric(12, 2))
    cash_pct = Column(Numeric(6, 3))
    portfolio_beta = Column(Numeric(6, 3))
    avg_pairwise_correlation = Column(Numeric(6, 3))
    sector_weights = Column(JSONB)
    position_weights = Column(JSONB)
    warnings = Column(JSONB)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())


class Position(Base):
    __tablename__ = "positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    company_name = Column(String(200))
    market = Column(String(10), nullable=False)
    sector = Column(String(100))
    is_etf = Column(Boolean, default=False)
    direction = Column(String(10))
    shares = Column(Integer)
    entry_price = Column(Numeric(12, 4))
    entry_date = Column(Date)
    entry_brokerage_aud = Column(Numeric(8, 2))
    entry_fx_cost_aud = Column(Numeric(8, 2))
    stop_loss = Column(Numeric(12, 4))
    target_1 = Column(Numeric(12, 4))
    target_2 = Column(Numeric(12, 4))
    notes = Column(Text)
    strategy_origin = Column(String(50))
    trade_idea_id = Column(UUID(as_uuid=True), ForeignKey("trade_ideas.id"), nullable=True)
    status = Column(String(20), default="open", index=True)
    exit_price = Column(Numeric(12, 4))
    exit_date = Column(Date)
    exit_brokerage_aud = Column(Numeric(8, 2))
    exit_fx_cost_aud = Column(Numeric(8, 2))
    exit_reason = Column(Text)
    gross_pnl_aud = Column(Numeric(12, 2))
    net_pnl_aud = Column(Numeric(12, 2))
    net_pnl_pct = Column(Numeric(8, 4))
    holding_days = Column(Integer)
    r_multiple = Column(Numeric(6, 2))
    max_adverse_excursion_pct = Column(Numeric(8, 4))
    max_favourable_excursion_pct = Column(Numeric(8, 4))
    regime_at_entry = Column(String(40))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))


class UserDecision(Base):
    __tablename__ = "user_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idea_id = Column(UUID(as_uuid=True), ForeignKey("trade_ideas.id"), nullable=True)
    confluence_id = Column(UUID(as_uuid=True), ForeignKey("confluence_alerts.id"), nullable=True)
    decision = Column(String(20))
    pass_reason = Column(String(100))
    size_choice = Column(String(40))
    suggested_value_aud = Column(Numeric(12, 2))
    actual_value_aud = Column(Numeric(12, 2))
    decided_at = Column(DateTime(timezone=True), server_default=func.now())
    market_regime = Column(String(40))
    notes = Column(Text)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_number = Column(Integer, nullable=False)
    total_decisions = Column(Integer)
    personalisation_data = Column(JSONB)
    prompt_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    active = Column(Boolean, default=False)


class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    market = Column(String(10), nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text)


class MarketBrief(Base):
    __tablename__ = "market_briefs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market = Column(String(10), nullable=False)
    brief_type = Column(String(20))
    content = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AIUsageLog(Base):
    __tablename__ = "ai_usage_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_type = Column(String(50))
    model = Column(String(50))
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    cost_usd = Column(Numeric(8, 4))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
