"""Notification delivery: WebSocket + email."""

import logging
from typing import Optional

from backend.alerts.engine import Alert, AlertSeverity

logger = logging.getLogger(__name__)


async def send_websocket_alert(alert: Alert) -> None:
    """Push alert to all connected WebSocket clients."""
    try:
        from backend.api.websockets import manager
        await manager.broadcast(alert.to_websocket_msg())
    except Exception as e:
        logger.error("WebSocket alert failed: %s", e)


async def send_email_alert(alert: Alert, to_email: Optional[str] = None) -> None:
    """Send email alert for critical notifications."""
    from backend.config import settings

    if not settings.sendgrid_api_key or settings.sendgrid_api_key == "optional":
        logger.debug("Email alerts not configured — skipping")
        return

    if not to_email:
        to_email = settings.alert_email

    if not to_email:
        return

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email="alerts@tradingassistant.local",
            to_emails=to_email,
            subject=f"[{alert.severity.value.upper()}] {alert.title}",
            plain_text_content=alert.message,
        )

        sg = SendGridAPIClient(settings.sendgrid_api_key)
        sg.send(message)
        logger.info("Email alert sent: %s", alert.title)

    except Exception as e:
        logger.error("Email alert failed: %s", e)


async def dispatch_alert(alert: Alert) -> None:
    """Route alert to appropriate channels based on severity."""
    # Always send to WebSocket
    await send_websocket_alert(alert)

    # Email for urgent/critical only
    if alert.severity in (AlertSeverity.URGENT, AlertSeverity.CRITICAL):
        await send_email_alert(alert)

    logger.info("Alert dispatched: [%s] %s", alert.severity.value, alert.title)
