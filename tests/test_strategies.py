"""Tests for strategies and position sizing."""

import pytest
from backend.strategies.base import (
    compute_sizing, TradeIdea, Direction, Conviction, TimeHorizon, IdeaStatus,
)


class TestPositionSizing:
    def test_asx_above_threshold(self):
        result = compute_sizing(
            entry=50.0, stop=47.0, market="ASX",
            portfolio_value_aud=5000, risk_pct=1.5,
        )
        assert result["shares"] > 0
        assert result["brokerage_aud"] == 0.0  # Above $1000
        assert result["fx_cost_aud"] == 0.0

    def test_asx_below_threshold(self):
        result = compute_sizing(
            entry=5.0, stop=4.5, market="ASX",
            portfolio_value_aud=5000, risk_pct=1.5,
        )
        # With $5 entry and small portfolio, likely under $1000
        if result["position_value_aud"] < 1000:
            assert result["brokerage_aud"] == 9.90

    def test_us_fx_cost(self):
        result = compute_sizing(
            entry=175.0, stop=170.0, market="NYSE",
            portfolio_value_aud=5000, risk_pct=1.5,
            aud_usd_rate=0.65, cmc_fx_spread_pct=0.0065,
        )
        assert result["fx_cost_aud"] > 0
        assert result["brokerage_aud"] == 0.0

    def test_zero_risk_returns_empty(self):
        result = compute_sizing(
            entry=50.0, stop=50.0, market="ASX",
            portfolio_value_aud=5000, risk_pct=1.5,
        )
        assert result["shares"] == 0

    def test_risk_off_regime_halves_risk(self):
        normal = compute_sizing(
            entry=50.0, stop=47.0, market="ASX",
            portfolio_value_aud=10000, risk_pct=2.0,
        )
        risk_off = compute_sizing(
            entry=50.0, stop=47.0, market="ASX",
            portfolio_value_aud=10000, risk_pct=2.0,
            regime="RISK_OFF_ELEVATED_FEAR",
        )
        assert risk_off["risk_amount_aud"] < normal["risk_amount_aud"]
        assert risk_off["risk_amount_aud"] == pytest.approx(normal["risk_amount_aud"] / 2, abs=1)

    def test_max_position_cap(self):
        result = compute_sizing(
            entry=1.0, stop=0.5, market="ASX",
            portfolio_value_aud=50000, risk_pct=5.0,
            max_position_pct=0.10,
        )
        assert result["position_value_aud"] <= 50000 * 0.10 + 1  # Rounding tolerance

    def test_small_trade_warning_asx(self):
        result = compute_sizing(
            entry=10.0, stop=9.0, market="ASX",
            portfolio_value_aud=2000, risk_pct=1.5,
        )
        if result["position_value_aud"] < 500:
            assert result["small_trade_warning"] is not None


class TestTradeIdea:
    def test_trade_idea_creation(self):
        idea = TradeIdea(
            symbol="BHP",
            company_name="BHP Group",
            market="ASX",
            sector="Materials",
            is_etf=False,
            strategy_name="dual_momentum",
            direction=Direction.LONG,
            conviction=Conviction.HIGH,
            time_horizon=TimeHorizon.POSITION,
        )
        assert idea.symbol == "BHP"
        assert idea.status == IdeaStatus.ACTIVE
        assert idea.direction == Direction.LONG

    def test_idea_defaults(self):
        idea = TradeIdea(
            symbol="CBA",
            company_name="CBA",
            market="ASX",
            sector="Financials",
            is_etf=False,
            strategy_name="trend_following",
            direction=Direction.LONG,
            conviction=Conviction.MEDIUM,
            time_horizon=TimeHorizon.SWING,
        )
        assert idea.confluence_score == 0.0
        assert idea.vas_overlap is False
        assert idea.ihvv_overlap is False
        assert idea.regime_compatible is True
        assert idea.created_at is not None


class TestMomentumStrategies:
    def test_dual_momentum_rsi(self):
        """Test RSI computation."""
        from backend.strategies.momentum.dual_momentum import DualMomentum
        import numpy as np
        # Uptrending prices should give RSI > 50
        closes = np.arange(50, 80, 0.5)
        rsi = DualMomentum._compute_rsi(closes)
        assert rsi is not None
        assert rsi > 50

    def test_dual_momentum_rsi_downtrend(self):
        from backend.strategies.momentum.dual_momentum import DualMomentum
        import numpy as np
        closes = np.arange(80, 50, -0.5)
        rsi = DualMomentum._compute_rsi(closes)
        assert rsi is not None
        assert rsi < 50

    def test_dual_momentum_ema(self):
        from backend.strategies.momentum.dual_momentum import DualMomentum
        import numpy as np
        closes = np.array([10.0] * 20 + [20.0] * 10)
        ema = DualMomentum._compute_ema(closes, 10)
        assert ema > 10.0  # Should be biased toward recent 20.0 values

    def test_trend_following_atr(self):
        from backend.strategies.momentum.trend_following import TrendFollowing
        from backend.data.normalizer import OHLCV
        from datetime import datetime, timezone
        bars = [
            OHLCV("TEST", "ASX", datetime.now(timezone.utc),
                   100 + i * 0.5, 102 + i * 0.5, 98 + i * 0.5, 101 + i * 0.5, 100000)
            for i in range(30)
        ]
        atr = TrendFollowing._atr(bars)
        assert atr is not None
        assert atr > 0

    def test_breakout_pattern_detection(self):
        from backend.strategies.momentum.breakout import Breakout
        import numpy as np
        # Flat highs, flat lows → flat base
        highs = np.array([10.0] * 15)
        lows = np.array([9.0] * 15)
        closes = np.array([9.5] * 15)
        pattern = Breakout._detect_pattern(highs, lows, closes)
        assert pattern == "flat base"
