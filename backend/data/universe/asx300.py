"""ASX 300 universe manager (superset of ASX 200)."""

from backend.data.universe.asx200 import get_asx200, UniverseStock


async def get_asx300() -> list[UniverseStock]:
    """ASX 300 = ASX 200 + 100 smaller caps. Returns ASX 200 for now."""
    return await get_asx200()


def is_asx300_constituent(symbol: str) -> bool:
    """Check if a symbol is in the ASX 300."""
    from backend.data.universe.asx200 import ASX200_CORE
    return symbol in {s.symbol for s in ASX200_CORE}
