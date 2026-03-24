"""Alert evaluation engine."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    NEW_IDEA = "new_idea"
    CONFLUENCE = "confluence_alert"
    POSITION = "position_alert"
    REGIME_CHANGE = "regime_change"
    RISK_WARNING = "risk_warning"
    IDEA_INVALIDATED = "idea_invalidated"
    EARNINGS_RISK = "earnings_risk"
    ANNOUNCEMENT = "announcement"
    PRICE_TARGET = "price_target"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    URGENT = "urgent"
    CRITICAL = "critical"


@dataclass
class Alert:
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    symbol: Optional[str] = None
    data: Optional[dict] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

    def to_websocket_msg(self) -> dict:
        return {
            "type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "symbol": self.symbol,
            "data": self.data,
            "timestamp": self.created_at.isoformat(),
        }


def create_confluence_alert(confluence_data: dict) -> Alert:
    tier = confluence_data.get("tier", 1)
    symbol = confluence_data.get("symbol", "")
    strategies = confluence_data.get("agreeing_strategies", [])

    severity = {1: AlertSeverity.INFO, 2: AlertSeverity.WARNING,
                3: AlertSeverity.URGENT, 4: AlertSeverity.CRITICAL}.get(tier, AlertSeverity.INFO)

    return Alert(
        alert_type=AlertType.CONFLUENCE,
        severity=severity,
        title=f"Confluence Tier {tier}: {symbol}",
        message=f"{len(strategies)} strategies agree: {', '.join(strategies)}",
        symbol=symbol,
        data=confluence_data,
    )


def create_regime_change_alert(market: str, old_regime: str, new_regime: str) -> Alert:
    return Alert(
        alert_type=AlertType.REGIME_CHANGE,
        severity=AlertSeverity.WARNING,
        title=f"Regime Change: {market}",
        message=f"{old_regime} → {new_regime}",
        data={"market": market, "old_regime": old_regime, "new_regime": new_regime},
    )


def create_risk_warning(warning_type: str, message: str) -> Alert:
    return Alert(
        alert_type=AlertType.RISK_WARNING,
        severity=AlertSeverity.WARNING,
        title=f"Risk: {warning_type}",
        message=message,
    )
