"""Backtesting framework for all strategies.

Usage:
    python -m backtests.runner --strategy all --market ASX --years 5
    python -m backtests.runner --strategy dual_momentum --market ASX --years 3
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.strategies.base import compute_sizing

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


@dataclass
class BacktestConfig:
    strategy: str
    market: str
    years: int
    portfolio_value: float = 5000.0
    risk_pct: float = 1.5
    slippage_pct: float = 0.1
    cmc_au_threshold: float = 1000.0
    cmc_au_fee: float = 9.90
    cmc_fx_spread: float = 0.0065


@dataclass
class BacktestResult:
    strategy: str
    market: str
    period: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return_pct: float
    annualized_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    avg_win_pct: float
    avg_loss_pct: float
    avg_r_multiple: float
    total_costs: float
    regime: Optional[str] = None
    survivorship_warning: str = (
        "WARNING: This backtest uses current index constituents. "
        "Survivorship bias means real-world performance may be lower."
    )

    def passes_thresholds(self) -> bool:
        """Check minimum performance thresholds."""
        return (
            self.sharpe_ratio > 0.5
            and self.win_rate > 0.38
            and self.max_drawdown_pct > -25
            and self.profit_factor > 1.3
            and self.total_trades >= 30
        )


def simulate_trades(
    prices: pd.DataFrame,
    signals: list[dict],
    config: BacktestConfig,
) -> BacktestResult:
    """
    Simulate trades from a list of signals against historical prices.

    signals: list of {symbol, entry_date, entry_price, stop, target1, target2, direction}
    prices: DataFrame with columns [symbol, date, close]
    """
    portfolio = config.portfolio_value
    trades = []
    peak = portfolio

    for signal in signals:
        entry = signal["entry_price"] * (1 + config.slippage_pct / 100)
        stop = signal["stop"]
        target = signal.get("target2", entry * 1.10)
        risk = abs(entry - stop)

        if risk <= 0:
            continue

        # Position sizing
        risk_aud = portfolio * (config.risk_pct / 100)
        shares = int(risk_aud / risk)
        if shares <= 0:
            continue

        position_value = shares * entry

        # Brokerage
        if config.market == "ASX":
            cost = 0 if position_value >= config.cmc_au_threshold else config.cmc_au_fee
        else:
            cost = position_value * config.cmc_fx_spread * 2

        # Simulate outcome (simplified: random walk based on actual statistics)
        # In production, walk through actual daily bars
        outcome = signal.get("outcome_pct", 0)
        pnl = position_value * (outcome / 100) - cost

        portfolio += pnl
        peak = max(peak, portfolio)

        trades.append({
            "symbol": signal["symbol"],
            "entry": entry,
            "exit": entry * (1 + outcome / 100),
            "pnl": pnl,
            "pnl_pct": outcome - (cost / position_value * 100),
            "r_multiple": outcome / (risk / entry * 100) if risk > 0 else 0,
            "cost": cost,
        })

    if not trades:
        return BacktestResult(
            strategy=config.strategy, market=config.market,
            period=f"{config.years}y", total_trades=0,
            winning_trades=0, losing_trades=0, win_rate=0,
            total_return_pct=0, annualized_return_pct=0,
            max_drawdown_pct=0, sharpe_ratio=0, profit_factor=0,
            avg_win_pct=0, avg_loss_pct=0, avg_r_multiple=0,
            total_costs=0,
        )

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    returns = [t["pnl_pct"] for t in trades]

    total_return = (portfolio - config.portfolio_value) / config.portfolio_value * 100
    ann_return = (1 + total_return / 100) ** (1 / max(config.years, 1)) - 1

    # Max drawdown
    equity_curve = [config.portfolio_value]
    for t in trades:
        equity_curve.append(equity_curve[-1] + t["pnl"])
    eq = np.array(equity_curve)
    peak_arr = np.maximum.accumulate(eq)
    drawdowns = (eq - peak_arr) / peak_arr * 100
    max_dd = float(np.min(drawdowns))

    # Sharpe
    if np.std(returns) > 0:
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252 / max(len(trades), 1))
    else:
        sharpe = 0

    # Profit factor
    gross_win = sum(t["pnl"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["pnl"] for t in losses)) if losses else 1
    pf = gross_win / gross_loss if gross_loss > 0 else 0

    return BacktestResult(
        strategy=config.strategy,
        market=config.market,
        period=f"{config.years}y",
        total_trades=len(trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
        win_rate=len(wins) / len(trades) if trades else 0,
        total_return_pct=round(total_return, 2),
        annualized_return_pct=round(ann_return * 100, 2),
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=round(sharpe, 2),
        profit_factor=round(pf, 2),
        avg_win_pct=round(np.mean([t["pnl_pct"] for t in wins]), 2) if wins else 0,
        avg_loss_pct=round(np.mean([t["pnl_pct"] for t in losses]), 2) if losses else 0,
        avg_r_multiple=round(np.mean([t["r_multiple"] for t in trades]), 2),
        total_costs=round(sum(t["cost"] for t in trades), 2),
    )


def generate_summary(results: list[BacktestResult]) -> str:
    """Generate SUMMARY.md from backtest results."""
    lines = [
        "# Backtest Results Summary",
        "",
        "**SURVIVORSHIP BIAS WARNING**: These backtests use current index constituents.",
        "Stocks that were delisted, merged, or dropped from the index are not included.",
        "Real-world performance will likely be lower than shown here.",
        "",
        "| Strategy | Market | Period | Trades | Win Rate | Return | Sharpe | Max DD | PF | Pass? |",
        "|----------|--------|--------|--------|----------|--------|--------|--------|-------|-------|",
    ]

    for r in results:
        passed = "YES" if r.passes_thresholds() else "NO"
        lines.append(
            f"| {r.strategy} | {r.market} | {r.period} | {r.total_trades} | "
            f"{r.win_rate:.0%} | {r.total_return_pct:+.1f}% | {r.sharpe_ratio:.2f} | "
            f"{r.max_drawdown_pct:.1f}% | {r.profit_factor:.2f} | {passed} |"
        )

    lines.extend([
        "",
        "## Minimum Thresholds",
        "- Sharpe > 0.5",
        "- Win rate > 38%",
        "- Max drawdown > -25%",
        "- Profit factor > 1.3",
        "- Minimum 30 trades",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run strategy backtests")
    parser.add_argument("--strategy", default="all", help="Strategy name or 'all'")
    parser.add_argument("--market", default="ASX", help="ASX or NYSE")
    parser.add_argument("--years", type=int, default=5, help="Years of history")
    args = parser.parse_args()

    print(f"Backtest runner: strategy={args.strategy}, market={args.market}, years={args.years}")
    print("NOTE: Full backtesting requires historical data download and database setup.")
    print("Run with Docker Compose for full functionality.")


if __name__ == "__main__":
    main()
