"""Auth event audit logging to database."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import insert

from backend.db.database import async_session
from backend.db.models import AuthAuditLog

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
    Log security events to auth_audit_log table.
    Never logs passwords or tokens — only metadata.
    """
    try:
        async with async_session() as session:
            stmt = insert(AuthAuditLog).values(
                id=uuid.uuid4(),
                event_type=event_type,
                user_id=uuid.UUID(user_id) if user_id else None,
                ip_address=ip_address,
                user_agent=user_agent,
                path=path,
                details=details,
                created_at=datetime.now(timezone.utc),
            )
            await session.execute(stmt)
            await session.commit()
    except Exception as e:
        # Audit logging should never crash the app
        logger.error("Failed to log auth event: %s %s", event_type, e)
