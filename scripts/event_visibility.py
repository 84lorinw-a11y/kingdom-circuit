"""Stable daily visibility boundaries, without changing recorded event dates.

Unknown end times retain the complete source calendar date. An explicit aware
end timestamp can prove an event finished before the Pacific daily rollover.
The result is input dependent, not dependent on the current wall clock, so it
is also safe for cached cards and browser calendar filtering.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import re
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


def _date(value):
    value = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _aware(value):
    if not isinstance(value, str) or "T" not in value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.utcoffset() is not None else None
    except ValueError:
        return None


def event_last_active_date(event):
    """Return the inclusive Pacific catalog date, preserving uncertain facts."""
    raw = str(event.get("endDate") or event.get("startDate") or "").strip()[:10]
    last = _date(raw)
    if last is None:
        return raw
    end = _aware(event.get("endDateTime")) or _aware(event.get("endDate"))
    if end is None or end.date() != last:
        return raw
    # Contradictory or incomplete source clocks must not cause early removal.
    clock = str(event.get("endTime") or "").strip()
    if clock and (not re.fullmatch(r"\d{2}:\d{2}(?::\d{2})?", clock)
                  or end.strftime("%H:%M:%S")[:len(clock)] != clock):
        return raw
    start_day = _date(event.get("startDate"))
    start = _aware(event.get("startDateTime")) or _aware(event.get("startDate"))
    if (start_day is not None and last < start_day) or (start is not None and end <= start):
        return raw
    start_clock = str(event.get("startTime") or "").strip()
    if start_day is not None and start_clock:
        try:
            if end.replace(tzinfo=None) <= datetime.combine(start_day, time.fromisoformat(start_clock)):
                return raw
        except ValueError:
            return raw
    # Midnight is exclusive: a show ending exactly at rollover is completed.
    # Never extend a date-only source boundary because of timezone conversion.
    try:
        effective = (end - timedelta(microseconds=1)).astimezone(PACIFIC).date()
    except (OverflowError, ValueError):
        return raw
    return min(last, effective).isoformat()


def event_is_past(event, cutoff):
    last = event_last_active_date(event)
    return _date(last) is not None and last < str(cutoff)
