"""Fundamental Value Screen strategy.

Weekly scan for quality companies trading at reasonable valuations.
"""

import logging
from typing import Optional
import numpy as np
import yfinance as yf

from backend.strategies.base import (
    BaseStrategy, TradeIdea, Direction, Conviction, TimeHorizon, compute_sizing,
)
from backend.data.feeds.yfinance_feed import get_daily_bars
from backend.data.universe.asx200 import is_top50_asx300
from backend.data.universe.sp500 import is_sp500_member
from backend.config import settings

logger = logging.getLogger(__name__)


class FundamentalScreen(BaseStrategy):
    name = "fundamental_screen"
    weight = 1.4

    async def generate_signals(self, universe: list, market: str) -> list[TradeIdea]:
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
        yf_sym = f"{stock.symbol}.AX" if market == "ASX" else stock.symbol

        try:
            ticker = yf.Ticker(yf_sym)
            info = ticker.info
        except Exception:
            return None

        # Profitability checks
        roe = info.get("returnOnEquity", 0) or 0
        if roe < 0.15:
            return None

        profit_margin = info.get("profitMargins", 0) or 0
        if profit_margin < 0.10:
            return None

        # Balance sheet
        de = info.get("debtToEquity", 999) or 999
        if de > 150:
            return None

        current_ratio = info.get("currentRatio", 0) or 0
        if current_ratio < 1.2:
            return None

        # Valuation
        pe = info.get("trailingPE", 0) or 0
        market_pe = 22 if market != "ASX" else 18
        if pe <= 0 or pe > market_pe * 1.5:
            return None

        peg = info.get("pegRatio", 0) or 0
        if peg > 1.5 and peg != 0:
            return None

        # Entry gate: technical
        price = float(info.get("currentPrice", info.get("regularMarketPrice", 0)))
        if price <= 0:
            return None

        low_52w = float(info.get("fiftyTwoWeekLow", price))
        sma200 = float(info.get("twoHundredDayAverage", price))

        near_52w_low = price < low_52w * 1.15
        near_sma200 = abs(price - sma200) / sma200 < 0.05

        bars = await get_daily_bars(stock.symbol, market, period="3mo")
        rsi = self._rsi(np.array([b.close for b in bars])) if len(bars) > 15 else 50

        if not (near_52w_low or near_sma200 or (rsi and rsi < 45)):
            return None

        entry = round(price, 4)
        stop = round(entry * 0.88, 4)  # 12% stop for investment horizon
        risk = entry - stop

        target_1 = round(sma200 * 1.1, 4)
        target_2 = round(entry * 1.25, 4)
        target_3 = round(entry * 1.40, 4)

        # Franking note for ASX
        fundamental_ctx = (
            f"ROE: {roe*100:.1f}%, Margin: {profit_margin*100:.1f}%, "
            f"D/E: {de:.0f}, P/E: {pe:.1f}, PEG: {peg:.2f}"
        )
        if market == "ASX":
            div_yield = info.get("dividendYield", 0) or 0
            fundamental_ctx += f", Div Yield: {div_yield*100:.1f}%"

        sizing = compute_sizing(
            entry, stop, market,
            settings.portfolio_value_aud, settings.risk_per_trade_pct,
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
            technical_summary=f"Value entry: near {'52w low' if near_52w_low else '200 SMA'}. RSI {rsi:.0f}.",
            risk_factors=["Value trap risk", "Sector headwinds"],
            invalidation_conditions=[
                f"Price breaks below {stop:.2f}",
                "Earnings downgrade > 10%",
            ],
            indicators={"pe": pe, "roe": round(roe, 3), "peg": peg, "rsi": rsi},
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
