"""Active decision capture and prompt evolution.

Tracks user decisions (act/pass) and learns preferences over time.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# One-click pass reasons
PASS_REASONS = [
    "Too risky",
    "Wrong timing",
    "Already exposed",
    "Don't know this stock",
    "Poor R/R",
    "Sector I avoid",
    "Price moved",
    "Just not feeling it",
]

# Position size choices
SIZE_CHOICES = [
    "Full suggested size",
    "Half size",
    "Smaller — testing",
    "Larger — high conviction",
]


def record_decision(
    idea_id: str,
    decision: str,  # 'acted' | 'passed' | 'watching'
    pass_reason: Optional[str] = None,
    size_choice: Optional[str] = None,
    suggested_value: Optional[float] = None,
    actual_value: Optional[float] = None,
) -> dict:
    """Record a user decision on an idea."""
    return {
        "idea_id": idea_id,
        "decision": decision,
        "pass_reason": pass_reason,
        "size_choice": size_choice,
        "suggested_value_aud": suggested_value,
        "actual_value_aud": actual_value,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }


def compute_style_profile(decisions: list[dict], trades: list[dict]) -> dict:
    """
    Compute user style profile from decision history.
    Called weekly to update the personalised AI prompt.
    """
    total = len(decisions)
    if total == 0:
        return {"total_decisions": 0}

    acted = [d for d in decisions if d["decision"] == "acted"]
    passed = [d for d in decisions if d["decision"] == "passed"]

    # Pass reason breakdown
    pass_reasons = {}
    for d in passed:
        reason = d.get("pass_reason", "Unknown")
        pass_reasons[reason] = pass_reasons.get(reason, 0) + 1

    # Size choice breakdown
    size_choices = {}
    for d in acted:
        choice = d.get("size_choice", "Unknown")
        size_choices[choice] = size_choices.get(choice, 0) + 1

    # Win rate by strategy (from closed trades)
    strategy_performance = {}
    for t in trades:
        strategy = t.get("strategy_origin", "unknown")
        if strategy not in strategy_performance:
            strategy_performance[strategy] = {"wins": 0, "losses": 0, "r_multiples": []}
        if t.get("net_pnl_aud", 0) > 0:
            strategy_performance[strategy]["wins"] += 1
        else:
            strategy_performance[strategy]["losses"] += 1
        if t.get("r_multiple"):
            strategy_performance[strategy]["r_multiples"].append(t["r_multiple"])

    win_rate_by_strategy = {}
    for s, perf in strategy_performance.items():
        total_trades = perf["wins"] + perf["losses"]
        if total_trades > 0:
            win_rate_by_strategy[s] = f"{perf['wins']/total_trades*100:.0f}%"

    # Best/worst strategies
    best = max(strategy_performance.items(), key=lambda x: x[1]["wins"], default=(None, {}))
    worst = min(
        strategy_performance.items(),
        key=lambda x: x[1]["wins"] / max(x[1]["wins"] + x[1]["losses"], 1),
        default=(None, {}),
    )

    # Average R-multiple
    all_r = [r for perf in strategy_performance.values() for r in perf["r_multiples"]]
    avg_r = sum(all_r) / len(all_r) if all_r else 0

    # Behavioural patterns
    patterns = []
    if len(size_choices.get("Half size", [])) > len(acted) * 0.4 if acted else False:
        patterns.append("size conservatively")
    top_pass = max(pass_reasons.items(), key=lambda x: x[1], default=("", 0))
    if top_pass[0]:
        patterns.append(f"frequently pass for: {top_pass[0]}")

    return {
        "total_decisions": total,
        "act_rate": len(acted) / total,
        "pass_rate": len(passed) / total,
        "pass_reasons": pass_reasons,
        "size_choices": size_choices,
        "win_rate_by_strategy": win_rate_by_strategy,
        "strongest_strategy": best[0] if best[0] else "N/A",
        "weakest_strategy": worst[0] if worst[0] else "N/A",
        "avg_r_multiple": avg_r,
        "behavioural_patterns": ", ".join(patterns) if patterns else "Not enough data yet",
        "top_sectors": "N/A",  # Computed from sector analysis
        "top_horizons": "N/A",
        "pass_rate_high": 0,
        "pass_rate_medium": 0,
        "preferred_sectors": "N/A",
        "avoided_sectors": "N/A",
    }


async def generate_weekly_report(
    decisions: list[dict],
    trades: list[dict],
    profile: dict,
) -> Optional[dict]:
    """
    Generate weekly style report using Claude.
    Runs Sunday 5 PM AEDT.
    """
    try:
        import anthropic
        from backend.config import settings

        if not settings.anthropic_api_key or settings.anthropic_api_key == "your_claude_api_key_here":
            return None

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        msg = f"""Generate a weekly trading style report based on this data:

Decisions this week: {len(decisions)}
Profile: {profile}

Structure:
1. This week by the numbers
2. What you acted on vs what you passed — pattern analysis
3. Your edge this week
4. One thing to do differently next week
5. Next week's setup"""

        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=1500,
            system="You are a trading performance coach. Be honest, data-driven, and specific.",
            messages=[{"role": "user", "content": msg}],
        )

        return {
            "content": response.content[0].text,
            "profile": profile,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Weekly report failed: %s", e)
        return None
