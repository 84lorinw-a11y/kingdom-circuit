#!/usr/bin/env python3
"""Ensure reviewed show additions and event artwork survive automation races."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPLEMENTAL = ROOT / "supplemental-events.json"
EVENTS = ROOT / "events.json"
MANUAL = ROOT / "config" / "manual-events.json"

GRACE_URL = "https://www.eventbrite.com/e/gracefest-2026-lecrae-bethel-music-jeremy-camp-tickets-1991972644803"
HVO_IMAGE = "assets/events/hvo-fest-2026.jpg"
TRUTHX_IMAGE = "assets/events/truthx-yung-kriss-2026.jpg"
GRACE_IMAGE = "assets/events/gracefest-2026.png"
HIP_HOP_IMAGE = "assets/events/hip-hop-in-the-park-2026.jpg"
REIGN_IMAGE = "assets/events/reign-volume-one-2026.jpg"
RARE_IMAGE = "assets/events/rare-of-breed-jacksonville-2026.jpg"
FLAVOR_FRIDAY_IMAGE = "assets/events/flavor-fest-friday-2026.webp"

PINNED_EVENT_IMAGES = {
    "Hip Hop in the Park": HIP_HOP_IMAGE,
    "GRACEFEST 2026": GRACE_IMAGE,
    "REIGN volume one": REIGN_IMAGE,
    "Rare of Breed": RARE_IMAGE,
    "Flavor Fest 2026 — Friday Concerts": FLAVOR_FRIDAY_IMAGE,
}

VERIFIED = [
    {
        "id": "eventbrite:truthx-yung-kriss-brandon-2026",
        "title": "TruthX Concert 2026",
        "startDate": "2026-09-12",
        "startTime": "19:00",
        "timezone": "America/New_York",
        "venue": "Brandon High School",
        "address": "1101 Victoria Street",
        "city": "Brandon",
        "state": "FL",
        "country": "US",
        "artists": ["Yung Kriss"],
        "headliner": "Yung Kriss",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/truthx-concert-2026-tickets-1989610293948",
        "officialUrl": "https://www.eventbrite.com/e/truthx-concert-2026-tickets-1989610293948",
        "image": TRUTHX_IMAGE,
        "imageType": "event_artwork",
        "imagePosition": "center",
        "imageOverride": True,
        "price": "",
        "sourceName": "Official Eventbrite listing",
        "authority": "venue_ticket",
        "confidence": "high",
        "lineupExplicit": True,
        "sources": [{"name": "Official Eventbrite listing", "url": "https://www.eventbrite.com/e/truthx-concert-2026-tickets-1989610293948", "type": "eventbrite", "authority": "venue_ticket", "priority": 94}],
    },
    {
        "id": "eventbrite:gracefest-lecrae-castaic-2026",
        "title": "GRACEFEST 2026",
        "startDate": "2026-09-19",
        "startTime": "13:30",
        "timezone": "America/Los_Angeles",
        "venue": "Castaic Lake State Recreation Area",
        "address": "Castaic Lake Drive",
        "city": "Castaic",
        "state": "CA",
        "country": "US",
        "artists": ["Lecrae"],
        "headliner": "Lecrae",
        "eventType": "festival",
        "status": "scheduled",
        "ticketUrl": GRACE_URL,
        "officialUrl": GRACE_URL,
        "image": GRACE_IMAGE,
        "imageType": "event_artwork",
        "imagePosition": "center",
        "imageOverride": True,
        "price": "",
        "sourceName": "Official Eventbrite listing",
        "authority": "official_festival",
        "confidence": "high",
        "lineupExplicit": True,
        "sources": [{"name": "Official Eventbrite listing", "url": GRACE_URL, "type": "eventbrite", "authority": "official_festival", "priority": 104}],
    },
    {
        "id": "eventbrite:hip-hop-in-the-park-cortland-2026",
        "title": "Hip Hop in the Park",
        "startDate": "2026-09-19",
        "startTime": "13:00",
        "timezone": "America/New_York",
        "venue": "Courthouse Park",
        "address": "33 Church Street",
        "city": "Cortland",
        "state": "NY",
        "country": "US",
        "artists": ["Datin", "Heesun Lee", "Brother Bo"],
        "headliner": "Datin",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/hip-hop-in-the-park-tickets-1999463357727",
        "officialUrl": "https://www.eventbrite.com/e/hip-hop-in-the-park-tickets-1999463357727",
        "image": HIP_HOP_IMAGE,
        "imageType": "event_artwork",
        "imagePosition": "center",
        "imageOverride": True,
        "price": "Free",
        "sourceName": "Official Eventbrite listing",
        "authority": "venue_ticket",
        "confidence": "high",
        "lineupExplicit": True,
        "sources": [{"name": "Official Eventbrite listing", "url": "https://www.eventbrite.com/e/hip-hop-in-the-park-tickets-1999463357727", "type": "eventbrite", "authority": "venue_ticket", "priority": 94}],
    },
    {
        "id": "eventbrite:reign-volume-one-aasha-marie-brooklyn-2026",
        "title": "REIGN volume one",
        "startDate": "2026-10-10",
        "startTime": "19:00",
        "timezone": "America/New_York",
        "venue": "The Vino Theater",
        "address": "274 Morgan Avenue, Suite 201",
        "city": "Brooklyn",
        "state": "NY",
        "country": "US",
        "artists": ["Aasha Marie"],
        "headliner": "Aasha Marie",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/reign-volume-one-tickets-1996068040241",
        "officialUrl": "https://www.eventbrite.com/e/reign-volume-one-tickets-1996068040241",
        "image": REIGN_IMAGE,
        "imageType": "event_artwork",
        "imagePosition": "center",
        "imageOverride": True,
        "price": "",
        "sourceName": "Official Eventbrite listing",
        "authority": "venue_ticket",
        "confidence": "high",
        "lineupExplicit": True,
        "sources": [{"name": "Official Eventbrite listing", "url": "https://www.eventbrite.com/e/reign-volume-one-tickets-1996068040241", "type": "eventbrite", "authority": "venue_ticket", "priority": 94}],
    },
    {
        "id": "eventbrite:rare-of-breed-jacksonville-2026",
        "title": "Rare of Breed",
        "startDate": "2026-10-16",
        "startTime": "19:00",
        "timezone": "America/New_York",
        "venue": "Murray Hill Theatre",
        "address": "932 Edgewood Ave S",
        "city": "Jacksonville",
        "state": "FL",
        "country": "US",
        "artists": ["Rare of Breed", "DJ Winn"],
        "headliner": "Rare of Breed",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/rare-of-breed-tickets-1986268845586",
        "officialUrl": "https://www.eventbrite.com/e/rare-of-breed-tickets-1986268845586",
        "image": RARE_IMAGE,
        "imageType": "event_artwork",
        "imagePosition": "center",
        "imageOverride": True,
        "price": "",
        "sourceName": "Official Eventbrite listing",
        "authority": "venue_ticket",
        "confidence": "high",
        "lineupExplicit": True,
        "sources": [{"name": "Official Eventbrite listing", "url": "https://www.eventbrite.com/e/rare-of-breed-tickets-1986268845586", "type": "eventbrite", "authority": "venue_ticket", "priority": 94}],
    },
    {
        "id": "flavor-fest-2026-friday-concerts",
        "title": "Flavor Fest 2026 — Friday Concerts",
        "startDate": "2026-11-06",
        "startTime": "19:00",
        "timezone": "America/New_York",
        "venue": "Crossover Church",
        "address": "1235 Fowler Ave",
        "city": "Tampa",
        "state": "FL",
        "country": "US",
        "artists": ["Miles Minnick", "Gifted Hands", "Datin"],
        "headliner": "Miles Minnick",
        "eventType": "festival",
        "status": "scheduled",
        "ticketUrl": "https://flavorfest.ticketspice.com/full-conference-",
        "officialUrl": "https://www.flavorfest.org/schedule",
        "image": FLAVOR_FRIDAY_IMAGE,
        "imageType": "event_artwork",
        "imagePosition": "center",
        "imageOverride": True,
        "price": "",
        "sourceName": "Flavor Fest official 2026 schedule",
        "authority": "official_event",
        "confidence": "high",
        "lineupExplicit": True,
        "sources": [{"name": "Flavor Fest official 2026 schedule", "url": "https://www.flavorfest.org/schedule", "type": "manual_verified", "authority": "official_event", "priority": 112}],
    },
]


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else []


def write(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def ensure_by_id(path: Path, additions: list[dict]) -> None:
    rows = load(path)
    by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}
    for event in additions:
        by_id[event["id"]] = event
    merged = list(by_id.values())
    merged.sort(key=lambda row: (str(row.get("startDate", "9999")), str(row.get("startTime", "")), str(row.get("title", ""))))
    write(path, merged)


def repair_live_events() -> None:
    rows = load(EVENTS)
    def verified_key(event: dict) -> tuple[str, str, str]:
        return (
            str(event.get("officialUrl") or event.get("ticketUrl") or "").strip(),
            str(event.get("startDate") or "").strip(),
            str(event.get("city") or "").strip().casefold(),
        )

    verified_keys = {
        verified_key(event)
        for event in VERIFIED
        if verified_key(event)[0]
    }
    cleaned = []
    seen_verified_keys = set()
    for event in rows:
        if not isinstance(event, dict):
            continue
        event_key = verified_key(event)
        if event_key in verified_keys:
            if event_key in seen_verified_keys:
                continue
            seen_verified_keys.add(event_key)
        if event.get("title") in PINNED_EVENT_IMAGES:
            event["image"] = PINNED_EVENT_IMAGES[event["title"]]
            event["imageType"] = "event_artwork"
            event["imagePosition"] = "center"
            event["imageOverride"] = True
        if event.get("id") in {
            "eventbrite:truthx-yung-kriss-brandon-2026",
            "manual:eventbrite:truthx-yung-kriss-brandon-2026",
        } or event.get("title") == "TruthX Concert 2026":
            event["image"] = TRUTHX_IMAGE
            event["imageType"] = "event_artwork"
            event["imagePosition"] = "center"
            event["imageOverride"] = True
        if event.get("id") == "manual:hvo-fest-2026-los-angeles" or event.get("title") == "HVO Fest 2026":
            event["image"] = HVO_IMAGE
            event["imageType"] = "event_artwork"
            event["imagePosition"] = "center"
            event["imageOverride"] = True
        if (
            event.get("startDate") == "2026-09-19"
            and str(event.get("city", "")).casefold() == "castaic"
            and any(str(a).casefold() == "lecrae" for a in event.get("artists", []))
        ):
            event.update({
                "title": "GRACEFEST 2026",
                "startTime": "13:30",
                "timezone": "America/Los_Angeles",
                "venue": "Castaic Lake State Recreation Area",
                "address": "Castaic Lake Drive",
                "eventType": "festival",
                "ticketUrl": GRACE_URL,
                "officialUrl": GRACE_URL,
                "sourceName": "Official Eventbrite listing",
                "authority": "official_festival",
                "confidence": "high",
                "lineupExplicit": True,
            })
            sources = [s for s in event.get("sources", []) if isinstance(s, dict)]
            if not any(s.get("url") == GRACE_URL for s in sources):
                sources.insert(0, {"name": "Official Eventbrite listing", "url": GRACE_URL, "type": "eventbrite", "authority": "official_festival", "priority": 104})
            event["sources"] = sources
        cleaned.append(event)
    write(EVENTS, cleaned)


def main() -> int:
    for image in (
        TRUTHX_IMAGE,
        HVO_IMAGE,
        GRACE_IMAGE,
        HIP_HOP_IMAGE,
        REIGN_IMAGE,
        RARE_IMAGE,
        FLAVOR_FRIDAY_IMAGE,
    ):
        if not (ROOT / image).is_file():
            raise SystemExit(f"Required event artwork is missing: {image}")
    ensure_by_id(SUPPLEMENTAL, VERIFIED)
    ensure_by_id(MANUAL, VERIFIED)
    repair_live_events()
    print(f"Ensured {len(VERIFIED)} reviewed shows plus HVO artwork")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
