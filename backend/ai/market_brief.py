"""Position-aware morning brief generation."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)

BRIEF_SYSTEM_PROMPT = """You are writing a personalised morning brief for an individual trader. Structure it in exactly four sections: (1) Their open positions and what to watch today, (2) Market context, (3) Today's top trade ideas, (4) Regime status. Be specific. Use numbers. No filler. The positions section comes first because that's what matters most right now. Provide one concrete sentence of assessment for each open position."""


async def generate_morning_brief(
    market: str,
    positions: list[dict],
    market_data: dict,
    top_ideas: list[dict],
    regime: str,
) -> Optional[dict]:
    """
    Generate position-aware morning brief.

    Sections:
    1. YOUR POSITIONS TODAY
    2. MARKET CONTEXT
    3. TODAY'S TOP IDEAS
    4. REGIME STATUS
    """
    try:
        import anthropic
    except ImportError:
        return None

    if not settings.anthropic_api_key or settings.anthropic_api_key == "your_claude_api_key_here":
        logger.warning("No API key — generating placeholder brief")
        return _placeholder_brief(market, positions, regime)

    # Build position section
    position_text = "OPEN POSITIONS:\n"
    if positions:
        for p in positions:
            pnl = ((p["current_price"] - p["entry_price"]) / p["entry_price"] * 100)
            stop_dist = ((p["current_price"] - p.get("stop_loss", 0)) / p["current_price"] * 100) if p.get("stop_loss") else None
            position_text += (
                f"- {p['symbol']}: Entry ${p['entry_price']:.2f}, "
                f"Current ${p['current_price']:.2f} ({pnl:+.1f}%), "
                f"Stop distance: {stop_dist:.1f}%\n" if stop_dist else
                f"- {p['symbol']}: Entry ${p['entry_price']:.2f}, "
                f"Current ${p['current_price']:.2f} ({pnl:+.1f}%)\n"
            )
    else:
        position_text += "No open positions.\n"

    user_msg = f"""Generate a morning brief for {market} market.

{position_text}

MARKET DATA:
{json.dumps(market_data, indent=2, default=str)}

TOP IDEAS TODAY:
{json.dumps([{{
    'symbol': i.get('symbol'),
    'strategy': i.get('strategy_name'),
    'conviction': i.get('conviction'),
    'entry': i.get('suggested_entry'),
}} for i in top_ideas[:3]], indent=2)}

CURRENT REGIME: {regime}

Provide a concise morning brief in the four required sections."""

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=BRIEF_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )

        return {
            "market": market,
            "content": response.content[0].text,
            "regime": regime,
            "position_count": len(positions),
            "idea_count": len(top_ideas),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Morning brief generation failed: %s", e)
        return _placeholder_brief(market, positions, regime)


def _placeholder_brief(market: str, positions: list, regime: str) -> dict:
    """Fallback brief when AI is unavailable."""
    return {
        "market": market,
        "content": (
            f"## {market} Morning Brief\n\n"
            f"**Positions:** {len(positions)} open\n"
            f"**Regime:** {regime}\n\n"
            "AI analysis unavailable — check API key configuration."
        ),
        "regime": regime,
        "position_count": len(positions),
        "idea_count": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
