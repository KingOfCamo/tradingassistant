"""Auth event audit logging."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def log_auth_event(
    event_type: str,
    ip_address: str | None = None,
    user_id: str | None = None,
    user_agent: str | None = None,
    path: str | None = None,
    details: dict | None = None,
) -> None:
    """
    Log security events. In production, writes to auth_audit_log table.
    Events: login_success, login_failure, logout, token_refresh,
    access_denied, suspicious_activity.
    """
    # TODO: Write to database auth_audit_log table
    logger.info(
        "AUTH_EVENT: type=%s user_id=%s ip=%s path=%s details=%s",
        event_type,
        user_id,
        ip_address,
        path,
        details,
    )
