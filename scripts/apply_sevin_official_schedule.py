#!/usr/bin/env python3
"""Replace malformed Sevin tour records with the canonical HOG MOB schedule.

The generic Sevin page parser can accidentally consume the nearby SPONSOR link
as part of a city name. This post-collection guard makes HOG MOB's official
Sevin concert page authoritative and keeps those malformed records from
reappearing after scheduled refreshes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
HOGMOB_URL = "https://hogmob.com/sevin-live-concert/"

SEVIN_EVENTS = [
    {
        "id": "sevin-live-san-diego-2026-08-29",
        "title": "Sevin Live Concert",
        "startDate": "2026-08-29",
        "startTime": "20:00",
        "venue": "Location TBD",
        "address": "",
        "city": "San Diego",
        "state": "CA",
        "country": "US",
        "artists": ["Sevin"],
        "headliner": "Sevin",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/1976534238113?aff=oddtdtcreator",
        "officialUrl": HOGMOB_URL,
        "image": "assets/artists/sevin.webp",
        "price": "Donate what you can; VIP $110",
        "sourceName": "HOG MOB official Sevin tour",
    },
    {
        "id": "sevin-live-kansas-city-2026-09-26",
        "title": "Sevin Live Concert",
        "startDate": "2026-09-26",
        "startTime": "20:00",
        "venue": "Location TBD",
        "address": "",
        "city": "Kansas City",
        "state": "MO",
        "country": "US",
        "artists": ["Sevin"],
        "headliner": "Sevin",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/1976535062579?aff=oddtdtcreator",
        "officialUrl": HOGMOB_URL,
        "image": "assets/artists/sevin.webp",
        "price": "Donate what you can; VIP $110",
        "sourceName": "HOG MOB official Sevin tour",
    },
    {
        "id": "sevin-live-nashville-2026-10-24",
        "title": "Sevin Live Concert",
        "startDate": "2026-10-24",
        "startTime": "20:00",
        "venue": "Location TBD",
        "address": "",
        "city": "Nashville",
        "state": "TN",
        "country": "US",
        "artists": ["Sevin"],
        "headliner": "Sevin",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/1976535113732?aff=oddtdtcreator",
        "officialUrl": HOGMOB_URL,
        "image": "assets/artists/sevin.webp",
        "price": "Donate what you can; VIP $110",
        "sourceName": "HOG MOB official Sevin tour",
    },
    {
        "id": "sevin-live-charlotte-2026-11-21",
        "title": "Sevin Live Concert",
        "startDate": "2026-11-21",
        "startTime": "20:00",
        "venue": "Location TBD",
        "address": "",
        "city": "Charlotte",
        "state": "NC",
        "country": "US",
        "artists": ["Sevin"],
        "headliner": "Sevin",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/1976534090672?aff=oddtdtcreator",
        "officialUrl": HOGMOB_URL,
        "image": "assets/artists/sevin.webp",
        "price": "Donate what you can; VIP $110",
        "sourceName": "HOG MOB official Sevin tour",
    },
    {
        "id": "sevin-live-sacramento-2026-12-05",
        "title": "Sevin Live Concert",
        "startDate": "2026-12-05",
        "startTime": "20:00",
        "venue": "Location TBD",
        "address": "",
        "city": "Sacramento",
        "state": "CA",
        "country": "US",
        "artists": ["Sevin"],
        "headliner": "Sevin",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/1976538907078?aff=oddtdtcreator",
        "officialUrl": HOGMOB_URL,
        "image": "assets/artists/sevin.webp",
        "price": "Donate what you can; VIP $110",
        "sourceName": "HOG MOB official Sevin tour",
    },
]

for event in SEVIN_EVENTS:
    event["authority"] = "artist_calendar"
    event["confidence"] = "high"
    event["lineupExplicit"] = True
    event["sources"] = [
        {
            "name": "HOG MOB official Sevin tour",
            "url": HOGMOB_URL,
            "type": "manual_verified",
            "authority": "artist_calendar",
            "priority": 100,
        },
        {
            "name": "Official ticket link from HOG MOB",
            "url": event["ticketUrl"],
            "type": "venue_ticket",
            "authority": "venue_ticket",
            "priority": 94,
        },
    ]

CANONICAL_IDS = {event["id"] for event in SEVIN_EVENTS}
CANONICAL_DATES = {event["startDate"] for event in SEVIN_EVENTS}


def load(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        value = []
    if not isinstance(value, list):
        raise SystemExit(f"Expected JSON array: {path}")
    return [item for item in value if isinstance(item, dict)]


def save(path: Path, value: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_sevin(event: dict[str, Any]) -> bool:
    artists = {str(name or "").strip().casefold() for name in event.get("artists", [])}
    return "sevin" in artists


def main() -> int:
    events = load(EVENTS_FILE)
    supplemental = load(SUPPLEMENTAL_FILE)

    before_events = len(events)
    events = [
        event for event in events
        if not (is_sevin(event) and str(event.get("startDate") or "") in CANONICAL_DATES)
    ]
    removed = before_events - len(events)

    supplemental = [
        event for event in supplemental
        if str(event.get("id") or "") not in CANONICAL_IDS
        and not (is_sevin(event) and str(event.get("startDate") or "") in CANONICAL_DATES)
    ]
    supplemental.extend(SEVIN_EVENTS)
    supplemental.sort(key=lambda event: (str(event.get("startDate") or "9999-12-31"), str(event.get("title") or "")))

    save(EVENTS_FILE, events)
    save(SUPPLEMENTAL_FILE, supplemental)

    all_published = [*events, *supplemental]
    malformed = [
        event for event in all_published
        if is_sevin(event) and str(event.get("city") or "").casefold().startswith("sponsor ")
    ]
    if malformed:
        raise SystemExit(f"Malformed Sevin city labels remain: {malformed}")

    for expected in SEVIN_EVENTS:
        matches = [
            event for event in all_published
            if is_sevin(event) and event.get("startDate") == expected["startDate"]
        ]
        if len(matches) != 1 or matches[0].get("city") != expected["city"]:
            raise SystemExit(f"Sevin canonicalization failed for {expected['startDate']}: {matches}")

    print(f"Sevin schedule normalized from HOG MOB: removed {removed} malformed/duplicate collected record(s); ensured {len(SEVIN_EVENTS)} official upcoming dates.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
