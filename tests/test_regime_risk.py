"""Tests for regime detection and portfolio heat map."""

import pytest
from backend.strategies.regime.detector import (
    classify_regime,
    MarketRegime,
    is_strategy_active,
    get_active_strategies,
    get_suppressed_strategies,
    compute_adx,
    REGIME_STRATEGY_MAP,
)
from backend.risk.portfolio_heat import (
    compute_portfolio_beta,
    compute_sector_weights,
    compute_warnings,
    simulate_position_impact,
    PositionRisk,
    PortfolioHeatMap,
)


class TestRegimeClassification:
    def test_crisis_extreme_fear(self):
        regime = classify_regime(vix=35, adx=10, breadth=0.30)
        assert regime == MarketRegime.CRISIS_EXTREME_FEAR

    def test_risk_off_elevated_fear(self):
        regime = classify_regime(vix=25, adx=15, breadth=0.40, ad_ratio=0.5)
        assert regime == MarketRegime.RISK_OFF_ELEVATED_FEAR

    def test_strong_trend_bull(self):
        regime = classify_regime(vix=12, adx=30, breadth=0.70)
        assert regime == MarketRegime.STRONG_TREND_BULL

    def test_choppy_range_bound(self):
        regime = classify_regime(vix=18, adx=15, breadth=0.50)
        assert regime == MarketRegime.CHOPPY_RANGE_BOUND

    def test_moderate_trend_bull_default(self):
        regime = classify_regime(vix=17, adx=22, breadth=0.55)
        assert regime == MarketRegime.MODERATE_TREND_BULL

    def test_none_values_default_moderate(self):
        regime = classify_regime(vix=None, adx=None, breadth=None)
        assert regime == MarketRegime.MODERATE_TREND_BULL


class TestStrategyGating:
    def test_momentum_active_in_bull(self):
        assert is_strategy_active("dual_momentum", MarketRegime.STRONG_TREND_BULL)

    def test_momentum_suppressed_in_choppy(self):
        assert not is_strategy_active("dual_momentum", MarketRegime.CHOPPY_RANGE_BOUND)

    def test_mean_reversion_suppressed_in_strong_bull(self):
        assert not is_strategy_active("bollinger_rsi", MarketRegime.STRONG_TREND_BULL)

    def test_fundamental_always_active(self):
        for regime in MarketRegime:
            assert is_strategy_active("fundamental_screen", regime)

    def test_all_strategies_active_in_moderate_bull(self):
        active = get_active_strategies(MarketRegime.MODERATE_TREND_BULL)
        assert len(active) == 9  # All 9 strategies

    def test_crisis_only_fundamental(self):
        active = get_active_strategies(MarketRegime.CRISIS_EXTREME_FEAR)
        assert active == ["fundamental_screen"]

    def test_suppressed_in_crisis(self):
        suppressed = get_suppressed_strategies(MarketRegime.CRISIS_EXTREME_FEAR)
        assert len(suppressed) == 8  # All except fundamental

    def test_all_regimes_have_mappings(self):
        for regime in MarketRegime:
            assert regime in REGIME_STRATEGY_MAP


class TestADXComputation:
    def test_adx_returns_none_for_insufficient_data(self):
        from backend.data.normalizer import OHLCV
        from datetime import datetime, timezone
        bars = [
            OHLCV("TEST", "ASX", datetime.now(timezone.utc), 10, 11, 9, 10, 1000)
            for _ in range(10)
        ]
        result = compute_adx(bars)
        assert result is None

    def test_adx_returns_float_for_sufficient_data(self):
        from backend.data.normalizer import OHLCV
        from datetime import datetime, timezone
        import random
        random.seed(42)
        bars = []
        price = 100.0
        for i in range(60):
            change = random.uniform(-2, 2.5)
            price = max(1, price + change)
            bars.append(OHLCV(
                "TEST", "ASX", datetime.now(timezone.utc),
                price - 0.5, price + 1, price - 1, price, 100000
            ))
        result = compute_adx(bars)
        assert result is not None
        assert 0 <= result <= 100


class TestPortfolioBeta:
    def _make_position(self, symbol, weight, beta, sector="Tech"):
        return PositionRisk(
            symbol=symbol, market="ASX", sector=sector, is_etf=False,
            shares=100, entry_price=10, current_price=10,
            current_value_aud=1000, weight_pct=weight, beta=beta, pnl_pct=0,
        )

    def test_single_position_beta(self):
        positions = [self._make_position("A", 100, 1.5)]
        assert compute_portfolio_beta(positions) == 1.5

    def test_weighted_beta(self):
        positions = [
            self._make_position("A", 60, 1.0),
            self._make_position("B", 40, 2.0),
        ]
        beta = compute_portfolio_beta(positions)
        assert abs(beta - 1.4) < 0.01

    def test_empty_portfolio(self):
        assert compute_portfolio_beta([]) == 0.0


class TestSectorWeights:
    def _make_position(self, symbol, weight, sector):
        return PositionRisk(
            symbol=symbol, market="ASX", sector=sector, is_etf=False,
            shares=100, entry_price=10, current_price=10,
            current_value_aud=1000, weight_pct=weight, beta=1.0, pnl_pct=0,
        )

    def test_single_sector(self):
        positions = [self._make_position("A", 50, "Financials")]
        weights = compute_sector_weights(positions)
        assert weights == {"Financials": 50}

    def test_multiple_sectors(self):
        positions = [
            self._make_position("A", 40, "Financials"),
            self._make_position("B", 30, "Materials"),
            self._make_position("C", 30, "Financials"),
        ]
        weights = compute_sector_weights(positions)
        assert weights["Financials"] == 70
        assert weights["Materials"] == 30


class TestRiskWarnings:
    def test_sector_concentration_warning(self):
        warnings = compute_warnings(
            {"Financials": 40.0, "Materials": 10.0},
            portfolio_beta=1.0,
            avg_correlation=0.3,
            cash_pct=0.5,
        )
        assert any("Financials" in w for w in warnings)

    def test_high_beta_warning(self):
        warnings = compute_warnings(
            {"Tech": 30.0},
            portfolio_beta=1.8,
            avg_correlation=0.3,
            cash_pct=0.5,
        )
        assert any("beta" in w.lower() for w in warnings)

    def test_correlation_warning(self):
        warnings = compute_warnings(
            {"Tech": 30.0},
            portfolio_beta=1.0,
            avg_correlation=0.85,
            cash_pct=0.5,
        )
        assert any("correlated" in w.lower() for w in warnings)

    def test_low_cash_warning(self):
        warnings = compute_warnings(
            {"Tech": 30.0},
            portfolio_beta=1.0,
            avg_correlation=0.3,
            cash_pct=0.05,
        )
        assert any("cash" in w.lower() for w in warnings)

    def test_no_warnings_healthy_portfolio(self):
        warnings = compute_warnings(
            {"Tech": 20.0, "Financials": 15.0},
            portfolio_beta=1.1,
            avg_correlation=0.4,
            cash_pct=0.5,
        )
        assert len(warnings) == 0


class TestPositionImpact:
    def test_simulation_adds_sector_weight(self):
        heat = PortfolioHeatMap(
            total_value_aud=10000,
            cash_pct=0.5,
            portfolio_beta=1.0,
            avg_pairwise_correlation=0.3,
            sector_weights={"Financials": 30.0, "Materials": 20.0},
            position_risks=[],
            warnings=[],
        )
        result = simulate_position_impact(heat, "BHP", "Materials", 1000, 1.2)
        assert result["sector"] == "Materials"
        assert "Materials" in result["sector_delta"]
        assert result["new_portfolio_beta"] > 0
