"""Position monitoring: track open positions against stops and targets."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PositionAlert:
    symbol: str
    alert_type: str  # 'near_stop', 'near_target', 'trailing_stop', 'earnings_risk'
    severity: str  # 'info', 'warning', 'urgent'
    message: str
    current_price: float
    reference_level: float
    distance_pct: float
    timestamp: datetime


def check_position(
    symbol: str,
    entry_price: float,
    current_price: float,
    stop_loss: float,
    target_1: float,
    target_2: Optional[float] = None,
) -> list[PositionAlert]:
    """Check a single position for alerts."""
    alerts = []
    now = datetime.now(timezone.utc)

    if current_price <= 0 or stop_loss <= 0:
        return alerts

    # Stop distance
    stop_dist_pct = (current_price - stop_loss) / current_price * 100

    if stop_dist_pct < 2:
        alerts.append(PositionAlert(
            symbol=symbol,
            alert_type="near_stop",
            severity="urgent",
            message=f"{symbol} is {stop_dist_pct:.1f}% from stop loss ({stop_loss:.2f})",
            current_price=current_price,
            reference_level=stop_loss,
            distance_pct=round(stop_dist_pct, 2),
            timestamp=now,
        ))
    elif stop_dist_pct < 5:
        alerts.append(PositionAlert(
            symbol=symbol,
            alert_type="near_stop",
            severity="warning",
            message=f"{symbol} is {stop_dist_pct:.1f}% from stop loss",
            current_price=current_price,
            reference_level=stop_loss,
            distance_pct=round(stop_dist_pct, 2),
            timestamp=now,
        ))

    # Target proximity
    if target_1 and target_1 > 0:
        target_dist_pct = (target_1 - current_price) / current_price * 100
        if 0 < target_dist_pct < 3:
            alerts.append(PositionAlert(
                symbol=symbol,
                alert_type="near_target",
                severity="info",
                message=f"{symbol} is {target_dist_pct:.1f}% from Target 1 ({target_1:.2f})",
                current_price=current_price,
                reference_level=target_1,
                distance_pct=round(target_dist_pct, 2),
                timestamp=now,
            ))
        elif target_dist_pct <= 0:
            alerts.append(PositionAlert(
                symbol=symbol,
                alert_type="near_target",
                severity="info",
                message=f"{symbol} has reached Target 1 ({target_1:.2f}). Consider partial exit.",
                current_price=current_price,
                reference_level=target_1,
                distance_pct=round(target_dist_pct, 2),
                timestamp=now,
            ))

    return alerts


def monitor_all_positions(positions: list[dict]) -> list[PositionAlert]:
    """Run position checks on all open positions."""
    all_alerts = []
    for p in positions:
        alerts = check_position(
            symbol=p["symbol"],
            entry_price=p["entry_price"],
            current_price=p["current_price"],
            stop_loss=p.get("stop_loss", 0),
            target_1=p.get("target_1", 0),
            target_2=p.get("target_2"),
        )
        all_alerts.extend(alerts)
    return all_alerts
