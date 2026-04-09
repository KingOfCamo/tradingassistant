"""Fundamental Value Screen strategy.

Weekly scan for quality companies trading at reasonable valuations.
Routes all data through DataRouter — no direct yfinance calls.
"""

import logging
from typing import Optional

import numpy as np

from backend.strategies.base import (
    BaseStrategy, TradeIdea, Direction, Conviction, TimeHorizon, compute_sizing,
)
from backend.data.feeds.yfinance_feed import get_daily_bars  # shim → DataRouter
from backend.data.universe.asx200 import is_top50_asx300
from backend.data.universe.sp500 import is_sp500_member
from backend.config import settings

logger = logging.getLogger(__name__)


class FundamentalScreen(BaseStrategy):
    name = "fundamental_screen"
    weight = 1.4

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
        # ASX fundamentals: no working free source yet. Skip the whole market
        # so we don't burn compute cycles on stocks we can't evaluate.
        if market == "ASX":
            logger.info(
                "FundamentalScreen: skipping ASX — no free fundamentals source "
                "(upgrade Twelve Data or wire an ASX fundamentals provider)"
            )
            return []

        ideas = []
        for stock in universe:
            try:
                idea = await self._evaluate(stock, market)
                if idea:
                    ideas.append(idea)
            except Exception as e:
                logger.error("FundamentalScreen error for %s: %s", stock.symbol, e)
        return ideas

    async def _evaluate(self, stock, market) -> Optional[TradeIdea]:
        from backend.data.feeds.data_router import get_data_router
        router = get_data_router()

        # Pull fundamentals from DataRouter (Finnhub on US, empty on ASX)
        metrics = await router.get_fundamentals(stock.symbol, market)
        if not metrics:
            return None

        # Profitability
        roe = metrics.get("roe") or 0
        if roe < 0.15:
            return None

        profit_margin = metrics.get("profit_margin") or 0
        if profit_margin < 0.10:
            return None

        # Balance sheet
        de = metrics.get("debt_to_equity")
        if de is not None and de > 150:
            return None

        current_ratio = metrics.get("current_ratio")
        if current_ratio is not None and current_ratio < 1.2:
            return None

        # Valuation
        pe = metrics.get("pe_ratio") or 0
        market_pe = 22 if market != "ASX" else 18
        if pe <= 0 or pe > market_pe * 1.5:
            return None

        peg = metrics.get("peg_ratio") or 0
        if 0 < peg > 1.5:
            return None

        # Live price — from DataRouter quote (Finnhub for US, TD for ASX)
        try:
            quote = await router.get_quote(stock.symbol, market)
            price = float(quote.price) if quote else 0
        except Exception:
            price = 0
        if price <= 0:
            return None

        low_52w = metrics.get("fifty_two_week_low") or price
        # 200 SMA — compute from bars since Finnhub doesn't provide it
        bars = await get_daily_bars(stock.symbol, market, period="1y")
        if len(bars) < 200:
            return None

        closes = np.array([b.close for b in bars])
        sma200 = float(np.mean(closes[-200:]))
        rsi = self._rsi(closes)

        near_52w_low = price < low_52w * 1.15 if low_52w > 0 else False
        near_sma200 = abs(price - sma200) / sma200 < 0.05 if sma200 > 0 else False

        if not (near_52w_low or near_sma200 or (rsi is not None and rsi < 45)):
            return None

        entry = round(price, 4)
        stop = round(entry * 0.88, 4)  # 12% stop for investment horizon
        risk = entry - stop
        if risk <= 0:
            return None

        target_1 = round(sma200 * 1.1, 4)
        target_2 = round(entry * 1.25, 4)
        target_3 = round(entry * 1.40, 4)

        fundamental_ctx = (
            f"ROE: {roe*100:.1f}%, Margin: {profit_margin*100:.1f}%, "
            f"P/E: {pe:.1f}, PEG: {peg:.2f}"
        )
        if de is not None:
            fundamental_ctx += f", D/E: {de:.0f}"
        if market == "ASX":
            div_yield = metrics.get("dividend_yield") or 0
            fundamental_ctx += f", Div Yield: {div_yield*100:.1f}%"

        sizing = compute_sizing(
            entry, stop, market,
            settings.portfolio_value_aud,
            settings.risk_per_trade_pct,
        )

        return TradeIdea(
            symbol=stock.symbol,
            company_name=stock.company_name,
            market=market,
            sector=stock.gics_sector,
            is_etf=False,
            strategy_name=self.name,
            direction=Direction.LONG,
            conviction=Conviction.HIGH if pe < market_pe * 0.8 else Conviction.MEDIUM,
            time_horizon=TimeHorizon.INVESTMENT,
            current_price=price,
            suggested_entry=entry,
            entry_range_low=round(entry * 0.97, 4),
            entry_range_high=round(entry * 1.02, 4),
            stop_loss=stop,
            target_1=target_1,
            target_2=target_2,
            target_3=target_3,
            risk_reward_ratio=round((target_2 - entry) / risk, 2) if risk > 0 else 0,
            suggested_shares=sizing["shares"],
            position_value_aud=sizing["position_value_aud"],
            risk_amount_aud=sizing["risk_amount_aud"],
            cmc_brokerage_aud=sizing["brokerage_aud"],
            cmc_fx_cost_aud=sizing["fx_cost_aud"],
            total_trade_cost_aud=sizing["total_cost_aud"],
            small_trade_warning=sizing["small_trade_warning"],
            key_factors=[
                f"ROE {roe*100:.0f}%, strong profitability",
                f"P/E {pe:.1f} (vs market {market_pe})",
                "Near 52-week low" if near_52w_low else "Near 200 SMA support",
            ],
            fundamental_context=fundamental_ctx,
            technical_summary=(
                f"Value entry: near {'52w low' if near_52w_low else '200 SMA'}. "
                f"RSI {rsi:.0f}." if rsi is not None else
                f"Value entry: near {'52w low' if near_52w_low else '200 SMA'}."
            ),
            risk_factors=["Value trap risk", "Sector headwinds"],
            invalidation_conditions=[
                f"Price breaks below {stop:.2f}",
                "Earnings downgrade > 10%",
            ],
            indicators={
                "pe": pe,
                "roe": round(roe, 3),
                "peg": peg,
                "rsi": rsi,
                "sma200": round(sma200, 4),
            },
            vas_overlap=is_top50_asx300(stock.symbol) if market == "ASX" else False,
            ihvv_overlap=is_sp500_member(stock.symbol) if market != "ASX" else False,
        )

    @staticmethod
    def _rsi(closes, period=14):
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes[-(period + 1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain, avg_loss = np.mean(gains), np.mean(losses)
        if avg_loss == 0:
            return 100.0
        return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)
