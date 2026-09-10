#!/usr/bin/env python3
"""Keep verified Fall 2026 CHH discoveries in the live event feed.

This is a narrow editorial guard for events that were verified from Eventbrite
or the official Flavor Fest schedule but were being dropped by automated
refresh/curation. It also pins the user-supplied HVO Fest artwork.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
MANUAL_FILE = ROOT / "config" / "manual-events.json"

EVENTBRITE_IDS = {
    "eventbrite:truthx-yung-kriss-brandon-2026",
    "eventbrite:gracefest-lecrae-castaic-2026",
    "eventbrite:hip-hop-in-the-park-cortland-2026",
    "eventbrite:reign-volume-one-aasha-marie-brooklyn-2026",
    "eventbrite:rare-of-breed-jacksonville-2026",
}

EVENTBRITE_IMAGE_OVERRIDES = {
    "eventbrite:rare-of-breed-jacksonville-2026": "assets/artists/rare-of-breed-primary.jpg",
}

HVO_SOURCE_ID = "hvo-fest-2026-los-angeles"
HVO_LIVE_ID = "manual:hvo-fest-2026-los-angeles"
HVO_ART = "assets/events/hvo-fest-2026.jpg"

FLAVOR_FRIDAY = {
    "id": "flavor-fest-2026-friday-concerts",
    "title": "Flavor Fest 2026 — Friday Concerts",
    "startDate": "2026-11-06",
    "startTime": "19:00",
    "timezone": "America/New_York",
    "venue": "Crossover Church",
    "address": "1235 E Fowler Ave",
    "city": "Tampa",
    "state": "FL",
    "country": "US",
    "artists": ["Miles Minnick", "Gifted Hands", "Datin"],
    "headliner": "Miles Minnick",
    "eventType": "festival",
    "ticketUrl": "https://flavorfest.ticketspice.com/full-conference-",
    "officialUrl": "https://www.flavorfest.org/schedule",
    "image": "",
    "price": "",
    "status": "scheduled",
    "lineupExplicit": True,
    "authority": "official_event",
    "sourceName": "Flavor Fest official 2026 schedule",
    "sources": [
        {
            "name": "Flavor Fest official 2026 schedule",
            "url": "https://www.flavorfest.org/schedule",
            "type": "manual_verified",
            "authority": "official_event",
            "priority": 112,
        }
    ],
    "confidence": "high",
}


def load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"{path} must contain a JSON array")
    return data


def write(path: Path, data: list[dict]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def upsert(events: list[dict], event: dict, aliases: set[str] | None = None) -> None:
    ids = {event["id"]}
    if aliases:
        ids |= aliases
    for index, current in enumerate(events):
        if current.get("id") in ids:
            events[index] = deepcopy(event)
            return
    events.append(deepcopy(event))


def sort_events(events: list[dict]) -> None:
    events.sort(key=lambda e: (str(e.get("startDate") or "9999-99-99"), str(e.get("startTime") or ""), str(e.get("title") or "")))


def main() -> None:
    for relative in [HVO_ART, *EVENTBRITE_IMAGE_OVERRIDES.values()]:
        if not (ROOT / relative).is_file():
            raise SystemExit(f"Required pinned artwork is missing: {relative}")

    events = load(EVENTS_FILE)
    supplemental = load(SUPPLEMENTAL_FILE)
    manual = load(MANUAL_FILE)
    manual_by_id = {str(item.get("id")): item for item in manual if item.get("id")}

    missing = sorted(EVENTBRITE_IDS - set(manual_by_id))
    if missing:
        raise SystemExit(f"Verified Eventbrite records missing from manual registry: {missing}")

    # Promote the five verified Eventbrite discoveries into the primary live feed.
    for event_id in sorted(EVENTBRITE_IDS):
        item = deepcopy(manual_by_id[event_id])
        item.setdefault("country", "US")
        item.setdefault("confidence", "high")
        if event_id in EVENTBRITE_IMAGE_OVERRIDES:
            item["image"] = EVENTBRITE_IMAGE_OVERRIDES[event_id]
            item["imageType"] = "artist"
        else:
            item.setdefault("imageType", "event_artwork" if item.get("image") else "artist")
        upsert(events, item)
        upsert(supplemental, item)

    # Pin HVO Fest to the actual uploaded flyer instead of unrelated Ticketmaster art.
    hvo = deepcopy(manual_by_id.get(HVO_SOURCE_ID) or {})
    if not hvo:
        raise SystemExit("HVO Fest manual source record is missing")
    hvo["id"] = HVO_LIVE_ID
    hvo["image"] = HVO_ART
    hvo["imageType"] = "event_artwork"
    hvo["imageOverride"] = True
    hvo.setdefault("country", "US")
    hvo.setdefault("confidence", "high")
    upsert(events, hvo, aliases={HVO_SOURCE_ID})

    # Keep the source registry itself aligned so future collectors inherit the art.
    hvo_manual = deepcopy(manual_by_id[HVO_SOURCE_ID])
    hvo_manual["image"] = HVO_ART
    hvo_manual["imageType"] = "event_artwork"
    hvo_manual["imageOverride"] = True
    upsert(manual, hvo_manual)

    # Flavor Fest officially lists Miles Minnick, Gifted Hands and Datin Friday night.
    upsert(manual, FLAVOR_FRIDAY)
    live_flavor = deepcopy(FLAVOR_FRIDAY)
    live_flavor["id"] = "manual:flavor-fest-2026-friday-concerts"
    upsert(events, live_flavor, aliases={FLAVOR_FRIDAY["id"]})

    sort_events(events)
    sort_events(supplemental)
    sort_events(manual)
    write(EVENTS_FILE, events)
    write(SUPPLEMENTAL_FILE, supplemental)
    write(MANUAL_FILE, manual)

    required_live = EVENTBRITE_IDS | {HVO_LIVE_ID, "manual:flavor-fest-2026-friday-concerts"}
    live_ids = {str(item.get("id")) for item in events}
    absent = sorted(required_live - live_ids)
    if absent:
        raise SystemExit(f"Verified live events missing after upsert: {absent}")

    print("Verified Eventbrite discoveries, Flavor Fest Friday, and HVO artwork are pinned in the live feed.")


if __name__ == "__main__":
    main()
