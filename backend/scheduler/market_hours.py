"""Market hours management with full DST support."""

from datetime import datetime, time, timedelta, timezone
from typing import Optional

import pytz
from workalendar.oceania import NewSouthWales
from workalendar.usa import UnitedStates


ASX_TZ = pytz.timezone("Australia/Sydney")
NYSE_TZ = pytz.timezone("America/New_York")

ASX_OPEN = time(10, 0)     # 10:00 AM AEDT/AEST
ASX_CLOSE = time(16, 0)    # 4:00 PM
ASX_AUCTION_END = time(16, 12)

NYSE_OPEN = time(9, 30)    # 9:30 AM ET
NYSE_CLOSE = time(16, 0)   # 4:00 PM ET

_asx_cal = NewSouthWales()
_us_cal = UnitedStates()


def _now_in_tz(tz) -> datetime:
    return datetime.now(timezone.utc).astimezone(tz)


def is_market_open(market: str) -> bool:
    """Check if a market is currently open for trading."""
    if market == "ASX":
        now = _now_in_tz(ASX_TZ)
        if not _asx_cal.is_working_day(now.date()):
            return False
        return ASX_OPEN <= now.time() < ASX_CLOSE
    elif market in ("NYSE", "NASDAQ", "US"):
        now = _now_in_tz(NYSE_TZ)
        if not _us_cal.is_working_day(now.date()):
            return False
        return NYSE_OPEN <= now.time() < NYSE_CLOSE
    return False


def next_open(market: str) -> datetime:
    """Get the next market open time in UTC."""
    if market == "ASX":
        tz = ASX_TZ
        cal = _asx_cal
        open_time = ASX_OPEN
    else:
        tz = NYSE_TZ
        cal = _us_cal
        open_time = NYSE_OPEN

    now = _now_in_tz(tz)
    candidate = now.date()

    # If market is currently open or past open today, move to tomorrow
    if cal.is_working_day(candidate) and now.time() >= open_time:
        candidate += timedelta(days=1)

    # Find next working day
    while not cal.is_working_day(candidate):
        candidate += timedelta(days=1)

    open_dt = tz.localize(datetime.combine(candidate, open_time))
    return open_dt.astimezone(timezone.utc)


def next_close(market: str) -> datetime:
    """Get the next market close time in UTC."""
    if market == "ASX":
        tz = ASX_TZ
        cal = _asx_cal
        close_time = ASX_CLOSE
    else:
        tz = NYSE_TZ
        cal = _us_cal
        close_time = NYSE_CLOSE

    now = _now_in_tz(tz)
    candidate = now.date()

    if not cal.is_working_day(candidate) or now.time() >= close_time:
        candidate += timedelta(days=1)
        while not cal.is_working_day(candidate):
            candidate += timedelta(days=1)

    close_dt = tz.localize(datetime.combine(candidate, close_time))
    return close_dt.astimezone(timezone.utc)


def minutes_to_close(market: str) -> Optional[int]:
    """Minutes until market close. None if market is closed."""
    if not is_market_open(market):
        return None

    if market == "ASX":
        now = _now_in_tz(ASX_TZ)
        close = datetime.combine(now.date(), ASX_CLOSE)
        close = ASX_TZ.localize(close)
    else:
        now = _now_in_tz(NYSE_TZ)
        close = datetime.combine(now.date(), NYSE_CLOSE)
        close = NYSE_TZ.localize(close)

    delta = close - now.replace(tzinfo=None)
    # Workaround for tz-aware comparison
    delta = close.replace(tzinfo=None) - now.replace(tzinfo=None)
    return max(0, int(delta.total_seconds() / 60))


def session_label(market: str) -> str:
    """Human-readable session status."""
    if is_market_open(market):
        mins = minutes_to_close(market)
        if mins and mins < 30:
            return f"Open — closing in {mins}min"
        return "Open"

    next_dt = next_open(market)
    now = datetime.now(timezone.utc)
    delta = next_dt - now

    hours = int(delta.total_seconds() / 3600)
    if hours < 1:
        mins = int(delta.total_seconds() / 60)
        return f"Closed — opens in {mins}min"
    elif hours < 24:
        return f"Closed — opens in {hours}h"
    else:
        days = int(hours / 24)
        return f"Closed — opens in {days}d"


def active_markets() -> list[str]:
    """Return list of currently open markets."""
    markets = []
    if is_market_open("ASX"):
        markets.append("ASX")
    if is_market_open("NYSE"):
        markets.append("NYSE")
        markets.append("NASDAQ")
    return markets


def should_scan_now(market: str) -> bool:
    """Whether we should run scans for this market right now."""
    return is_market_open(market)


def format_local_time(dt: datetime, market: str) -> str:
    """Format a UTC datetime to local time for display."""
    if market == "ASX":
        local = dt.astimezone(ASX_TZ)
        return local.strftime("%I:%M %p AEDT" if local.dst() else "%I:%M %p AEST")
    else:
        local = dt.astimezone(NYSE_TZ)
        return local.strftime("%I:%M %p ET")
