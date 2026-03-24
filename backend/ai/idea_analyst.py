"""Claude AI analysis for trade ideas — adaptive personalised prompts."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.config import settings
from backend.ai.prompt_builder import build_personalised_system_prompt

logger = logging.getLogger(__name__)

RESPONSE_FORMAT = """{
  "bull_case": "3-4 specific evidence-based points",
  "bear_case": "3-4 specific risks and failure modes",
  "key_levels": ["string"],
  "ideal_entry_conditions": "string",
  "position_management": "string",
  "cmc_cost_note": "string | null",
  "regime_note": "string | null",
  "confluence_note": "string | null",
  "verdict": "STRONG_INTEREST | WATCH | PASS",
  "verdict_reasoning": "2-3 sentences",
  "updated_conviction": "high | medium | low",
  "analysis_confidence": 0.0
}"""


async def analyze_idea(
    idea_data: dict,
    user_history: Optional[dict] = None,
    regime_context: str = "",
    portfolio_context: str = "",
) -> Optional[dict]:
    """
    Run Claude analysis on a trade idea with adaptive personalised prompt.

    Returns parsed JSON analysis or None on failure.
    """
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed")
        return None

    if not settings.anthropic_api_key or settings.anthropic_api_key == "your_claude_api_key_here":
        logger.warning("No Anthropic API key configured — skipping AI analysis")
        return None

    system_prompt = await build_personalised_system_prompt(user_history)

    # Build user message with full context
    user_msg = f"""Analyze this trade idea and respond with ONLY valid JSON (no markdown).

TRADE IDEA:
Symbol: {idea_data.get('symbol')} ({idea_data.get('market')})
Company: {idea_data.get('company_name')}
Sector: {idea_data.get('sector')}
Strategy: {idea_data.get('strategy_name')}
Direction: {idea_data.get('direction')}
Conviction: {idea_data.get('conviction')}

PRICE LEVELS:
Current: ${idea_data.get('current_price')}
Entry: ${idea_data.get('suggested_entry')} (range: ${idea_data.get('entry_range_low')}-${idea_data.get('entry_range_high')})
Stop: ${idea_data.get('stop_loss')}
Target 1: ${idea_data.get('target_1')}
Target 2: ${idea_data.get('target_2')}
R/R: {idea_data.get('risk_reward_ratio')}

SIZING:
Shares: {idea_data.get('suggested_shares')}
Position value: ${idea_data.get('position_value_aud')} AUD
Risk: ${idea_data.get('risk_amount_aud')} AUD
Brokerage: ${idea_data.get('cmc_brokerage_aud')} + FX: ${idea_data.get('cmc_fx_cost_aud')}

KEY FACTORS:
{json.dumps(idea_data.get('key_factors', []), indent=2)}

TECHNICAL:
{idea_data.get('technical_summary', '')}

FUNDAMENTAL:
{idea_data.get('fundamental_context', '')}

INDICATORS:
{json.dumps(idea_data.get('indicators', {}), indent=2)}
"""

    if regime_context:
        user_msg += f"\nMARKET REGIME:\n{regime_context}\n"

    if portfolio_context:
        user_msg += f"\nPORTFOLIO IMPACT:\n{portfolio_context}\n"

    if idea_data.get('confluence_score', 0) > 0:
        user_msg += (
            f"\nCONFLUENCE: {idea_data.get('confluence_score')} score, "
            f"tier {idea_data.get('confluence_tier')}. "
            f"Multiple independent strategies agree on this setup.\n"
        )

    if idea_data.get('vas_overlap') or idea_data.get('ihvv_overlap'):
        user_msg += f"\nETF OVERLAP: {idea_data.get('overlap_note', '')}\n"

    user_msg += f"\nRespond with ONLY this JSON format:\n{RESPONSE_FORMAT}"

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )

        content = response.content[0].text.strip()
        # Parse JSON response
        analysis = json.loads(content)

        # Log usage
        logger.info(
            "AI analysis for %s: verdict=%s, tokens=%d/%d",
            idea_data.get("symbol"),
            analysis.get("verdict"),
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        return analysis

    except json.JSONDecodeError as e:
        logger.error("Failed to parse AI response as JSON: %s", e)
        return None
    except Exception as e:
        logger.error("AI analysis failed for %s: %s", idea_data.get("symbol"), e)
        return None
