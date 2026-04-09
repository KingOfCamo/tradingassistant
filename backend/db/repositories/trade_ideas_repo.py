"""Trade idea persistence layer.

Scan cycles write TradeIdea dataclasses here and the /api/ideas routes
read from here. Each scan archives prior active ideas for the same
(market) pair then inserts the fresh batch, so the feed never
accumulates stale duplicates.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import async_session
from backend.db.models import TradeIdeaModel
from backend.strategies.base import TradeIdea

logger = logging.getLogger(__name__)


# ─── helpers ──────────────────────────────────────────────────────────────


def _dataclass_to_row(idea: TradeIdea) -> dict:
    """Map a TradeIdea dataclass to a row dict for TradeIdeaModel."""
    d = asdict(idea) if is_dataclass(idea) else dict(idea)

    # Enum → string
    for k in ("direction", "conviction", "time_horizon", "status", "ai_conviction_override"):
        v = d.get(k)
        if v is not None and hasattr(v, "value"):
            d[k] = v.value

    # Drop any keys that aren't columns on TradeIdeaModel
    column_names = {c.name for c in TradeIdeaModel.__table__.columns}
    return {k: v for k, v in d.items() if k in column_names}


def _row_to_dict(row: TradeIdeaModel) -> dict:
    """Serialise a row to a JSON-safe dict for API responses."""
    data: dict = {}
    for col in TradeIdeaModel.__table__.columns:
        v = getattr(row, col.name)
        if isinstance(v, (datetime,)):
            data[col.name] = v.isoformat() if v else None
        elif isinstance(v, uuid.UUID):
            data[col.name] = str(v)
        elif hasattr(v, "__float__") and not isinstance(v, (int, float, bool)):
            # SQLAlchemy Decimal
            try:
                data[col.name] = float(v)
            except Exception:
                data[col.name] = None
        else:
            data[col.name] = v
    return data


# ─── public API ───────────────────────────────────────────────────────────


async def save_scan_ideas(ideas: list[TradeIdea], market: str) -> int:
    """Persist a fresh scan result.

    Archives every prior 'active' idea for this market (sets status to
    'archived' + status_reason), then inserts the new batch.
    Returns the number of new rows written.
    """
    if not ideas:
        # Still archive previous active ideas for this market so the feed
        # reflects "no ideas found this scan"
        async with async_session() as session:
            await _archive_active(session, market, reason="superseded_by_empty_scan")
            await session.commit()
        return 0

    async with async_session() as session:
        await _archive_active(session, market, reason="superseded_by_new_scan")

        count = 0
        for idea in ideas:
            try:
                row = _dataclass_to_row(idea)
                row["market"] = market  # defensive — make sure market is set
                row.setdefault("status", "active")
                # Nullable TIMESTAMPTZ fields need real datetimes
                if row.get("data_as_of") is None:
                    row["data_as_of"] = datetime.now(timezone.utc)
                session.add(TradeIdeaModel(**row))
                count += 1
            except Exception as e:
                logger.warning("Failed to persist idea %s: %s", getattr(idea, "symbol", "?"), e)
        await session.commit()
        logger.info("Persisted %d new %s ideas", count, market)
        return count


async def _archive_active(session: AsyncSession, market: str, reason: str) -> int:
    """Mark all currently-active ideas for a market as archived."""
    stmt = (
        update(TradeIdeaModel)
        .where(
            and_(
                TradeIdeaModel.market == market,
                TradeIdeaModel.status == "active",
            )
        )
        .values(status="archived", status_reason=reason)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def list_active_ideas(
    market: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Return active ideas, optionally filtered by market."""
    async with async_session() as session:
        stmt = select(TradeIdeaModel).where(TradeIdeaModel.status == "active")
        if market and market.upper() != "ALL":
            stmt = stmt.where(TradeIdeaModel.market == market.upper())
        stmt = stmt.order_by(
            TradeIdeaModel.confluence_score.desc().nullslast(),
            TradeIdeaModel.created_at.desc(),
        ).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return [_row_to_dict(r) for r in rows]


async def get_idea(idea_id: str) -> Optional[dict]:
    try:
        uid = uuid.UUID(idea_id)
    except ValueError:
        return None
    async with async_session() as session:
        stmt = select(TradeIdeaModel).where(TradeIdeaModel.id == uid)
        row = (await session.execute(stmt)).scalar_one_or_none()
        return _row_to_dict(row) if row else None


async def list_history(limit: int = 100) -> list[dict]:
    """Return non-active (archived/expired/etc) ideas for the history view."""
    async with async_session() as session:
        stmt = (
            select(TradeIdeaModel)
            .where(TradeIdeaModel.status != "active")
            .order_by(TradeIdeaModel.created_at.desc())
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [_row_to_dict(r) for r in rows]


async def record_user_action(
    idea_id: str,
    action: str,
    pass_reason: Optional[str] = None,
    notes: Optional[str] = None,
) -> bool:
    try:
        uid = uuid.UUID(idea_id)
    except ValueError:
        return False
    async with async_session() as session:
        stmt = (
            update(TradeIdeaModel)
            .where(TradeIdeaModel.id == uid)
            .values(
                user_action=action,
                user_pass_reason=pass_reason,
                user_notes=notes,
                user_action_at=datetime.now(timezone.utc),
            )
        )
        result = await session.execute(stmt)
        await session.commit()
        return (result.rowcount or 0) > 0
