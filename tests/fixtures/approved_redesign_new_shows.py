"""Exact New Shows filter excerpts from the approved redesign pin.

Source: 84lorinw-a11y/kingdom-circuit-test, scripts/apply_test_redesign.py
Commit: 66751f756158fae6c2682e34f7da12306bd133ab
Kept offline because production CI tests run before the pinned checkout.
"""
from __future__ import annotations

import datetime as dt
import html
import re
from typing import Iterable
from zoneinfo import ZoneInfo


SITE_TIMEZONE = ZoneInfo("America/Los_Angeles")


NEW_WINDOW_DAYS = 7


INACTIVE_STATUSES = {"cancelled", "canceled", "postponed", "merged"}


EVENT_CARD_PATTERN = re.compile(
    r'<article\b(?=[^>]*\bdata-event-card\b)[^>]*>.*?</article>',
    re.I | re.S,
)


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())


def normalized_key(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def event_source_key(event: dict[str, object]) -> tuple[str, str, str]:
    return (
        normalized_key(event.get("title")),
        str(event.get("startDate") or "")[:10],
        normalized_key(event.get("city")),
    )


def recent_event_keys(
    source_events: Iterable[dict[str, object]],
    today: dt.date,
    days: int = NEW_WINDOW_DAYS,
) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for event in source_events:
        if normalized_key(event.get("status")) in INACTIVE_STATUSES:
            continue
        raw_seen = str(event.get("firstSeen") or "").strip()
        if not raw_seen:
            continue
        try:
            seen = dt.datetime.fromisoformat(raw_seen.replace("Z", "+00:00"))
        except ValueError:
            continue
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=dt.timezone.utc)
        age = (today - seen.astimezone(SITE_TIMEZONE).date()).days
        if 0 <= age < days:
            keys.add(event_source_key(event))
    return keys


def attribute(fragment: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}=(?:\"([^\"]*)\"|'([^']*)')", fragment)
    if not match:
        return ""
    return html.unescape(match.group(1) if match.group(1) is not None else match.group(2))


def event_cards(document: str) -> list[str]:
    return EVENT_CARD_PATTERN.findall(document)


def card_source_key(card: str) -> tuple[str, str, str]:
    opening = card[: card.find(">") + 1]
    title_match = re.search(r'<h3>\s*<a\b[^>]*>(.*?)</a>', card, re.I | re.S)
    title = clean_text(title_match.group(1)) if title_match else ""
    location_match = re.search(
        r'<dt>\s*Location\s*</dt>\s*<dd>(.*?)</dd>',
        card,
        re.I | re.S,
    )
    location = clean_text(location_match.group(1)) if location_match else ""
    city = location.rsplit(",", 1)[0].strip() if "," in location else location
    return (
        normalized_key(title),
        attribute(opening, "data-date")[:10],
        normalized_key(city),
    )


def update_results_count(document: str) -> str:
    count = len(event_cards(document))
    return re.sub(
        r'(<[^>]+\bdata-results-count\b[^>]*>).*?(</[^>]+>)',
        rf"\g<1>{count} show{'s' if count != 1 else ''}\g<2>",
        document,
        flags=re.I | re.S,
    )


def transform_new_shows(
    document: str,
    recent_keys: set[tuple[str, str, str]],
) -> str:
    document = EVENT_CARD_PATTERN.sub(
        lambda match: match.group(0) if card_source_key(match.group(0)) in recent_keys else "",
        document,
    )
    document = re.sub(r"\b14 days\b", "7 days", document, flags=re.I)
    return update_results_count(document)
