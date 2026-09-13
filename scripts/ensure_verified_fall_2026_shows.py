#!/usr/bin/env python3
"""Keep verified Fall 2026 CHH discoveries in the live event feed.

This is a narrow editorial guard for events that were verified from Eventbrite
or the official Flavor Fest schedule but were being dropped by automated
refresh/curation. It also pins the user-supplied HVO Fest artwork. This guard
is deployment-critical because it protects the live catalog.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
MANUAL_FILE = ROOT / "config" / "manual-events.json"

RARE_ID = "eventbrite:rare-of-breed-jacksonville-2026"
RARE_CANCEL_URL = "https://www.eventbrite.com/e/cancelled-rare-of-breed-tickets-1986268845586"

EVENTBRITE_IDS = {
    "eventbrite:truthx-yung-kriss-brandon-2026",
    "eventbrite:gracefest-lecrae-castaic-2026",
    "eventbrite:hip-hop-in-the-park-cortland-2026",
    "eventbrite:reign-volume-one-aasha-marie-brooklyn-2026",
    RARE_ID,
}

EVENTBRITE_IMAGE_OVERRIDES = {
    "eventbrite:truthx-yung-kriss-brandon-2026": "assets/events/truthx-yung-kriss-2026.jpg",
    "eventbrite:gracefest-lecrae-castaic-2026": "assets/events/gracefest-2026.png",
    "eventbrite:hip-hop-in-the-park-cortland-2026": "assets/events/hip-hop-in-the-park-2026.jpg",
    "eventbrite:reign-volume-one-aasha-marie-brooklyn-2026": "assets/events/reign-volume-one-2026.jpg",
    RARE_ID: "assets/events/rare-of-breed-jacksonville-2026.jpg",
}

HVO_SOURCE_ID = "hvo-fest-2026-los-angeles"
HVO_LIVE_ID = "manual:hvo-fest-2026-los-angeles"
HVO_ART = "assets/events/hvo-fest-2026.jpg"
FLAVOR_FRIDAY_ART = "assets/events/flavor-fest-friday-2026.webp"

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
    "image": FLAVOR_FRIDAY_ART,
    "imageType": "event_artwork",
    "imagePosition": "center",
    "imageOverride": True,
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


def merge_sources(primary: list, secondary: list) -> list:
    merged: list = []
    seen: set[str] = set()
    for source in [*primary, *secondary]:
        if not isinstance(source, dict):
            continue
        key = str(source.get("url") or "").strip() or json.dumps(source, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        merged.append(deepcopy(source))
    return merged


def preserve_confirmed_cancellation(incoming: dict, current: dict) -> dict:
    """Never let a catalog-pinning guard downgrade confirmed cancellation evidence."""
    if current.get("status") != "cancelled" and not current.get("cancellationConfirmed"):
        return incoming
    result = deepcopy(incoming)
    result["status"] = "cancelled"
    result["cancellationConfirmed"] = True
    for key in (
        "cancellationConfirmedAt",
        "officialUrl",
        "ticketUrl",
        "sourceName",
        "notes",
        "ticketAvailability",
    ):
        if current.get(key) not in (None, ""):
            result[key] = deepcopy(current[key])
    result["sources"] = merge_sources(current.get("sources", []), result.get("sources", []))
    return result


def apply_known_durable_state(event_id: str, item: dict) -> dict:
    """Apply confirmed editorial states that supersede an older source snapshot."""
    result = deepcopy(item)
    if event_id == RARE_ID:
        result["status"] = "cancelled"
        result["cancellationConfirmed"] = True
        result["cancellationConfirmedAt"] = "2026-09-12"
        result["officialUrl"] = RARE_CANCEL_URL
        result["ticketUrl"] = RARE_CANCEL_URL
        result["sourceName"] = "Official Eventbrite cancellation notice"
        result["notes"] = "Cancelled by the organizer. This page is retained as a cancellation notice."
        cancellation_source = {
            "name": "Official Eventbrite cancellation notice",
            "url": RARE_CANCEL_URL,
            "type": "eventbrite",
            "authority": "venue_ticket",
            "priority": 120,
        }
        result["sources"] = merge_sources([cancellation_source], result.get("sources", []))
    return result


def upsert(events: list[dict], event: dict, aliases: set[str] | None = None) -> None:
    ids = {event["id"]}
    if aliases:
        ids |= aliases
    official_url = str(event.get("officialUrl") or event.get("ticketUrl") or "").strip()
    matches = [
        index
        for index, current in enumerate(events)
        if current.get("id") in ids
        or (
            official_url
            and str(current.get("officialUrl") or current.get("ticketUrl") or "").strip() == official_url
        )
    ]
    if not matches:
        events.append(deepcopy(event))
        return
    events[matches[0]] = preserve_confirmed_cancellation(deepcopy(event), events[matches[0]])
    for index in reversed(matches[1:]):
        del events[index]


def sort_events(events: list[dict]) -> None:
    events.sort(key=lambda e: (str(e.get("startDate") or "9999-99-99"), str(e.get("startTime") or ""), str(e.get("title") or "")))


def main() -> None:
    for relative in [HVO_ART, FLAVOR_FRIDAY_ART, *EVENTBRITE_IMAGE_OVERRIDES.values()]:
        if not (ROOT / relative).is_file():
            raise SystemExit(f"Required pinned artwork is missing: {relative}")

    events = load(EVENTS_FILE)
    supplemental = load(SUPPLEMENTAL_FILE)
    manual = load(MANUAL_FILE)
    manual_by_id = {str(item.get("id")): item for item in manual if item.get("id")}

    missing = sorted(EVENTBRITE_IDS - set(manual_by_id))
    if missing:
        raise SystemExit(f"Verified Eventbrite records missing from manual registry: {missing}")

    for event_id in sorted(EVENTBRITE_IDS):
        item = deepcopy(manual_by_id[event_id])
        item.setdefault("country", "US")
        item.setdefault("confidence", "high")
        if event_id in EVENTBRITE_IMAGE_OVERRIDES:
            item["image"] = EVENTBRITE_IMAGE_OVERRIDES[event_id]
            item["imageType"] = "event_artwork"
            item["imagePosition"] = "center"
            item["imageOverride"] = True
        else:
            item.setdefault("imageType", "event_artwork" if item.get("image") else "artist")
        item = apply_known_durable_state(event_id, item)
        live_item = deepcopy(item)
        live_item["id"] = f"manual:{event_id}"
        upsert(events, live_item, aliases={event_id})
        upsert(supplemental, item)
        upsert(manual, item)

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

    hvo_manual = deepcopy(manual_by_id[HVO_SOURCE_ID])
    hvo_manual["image"] = HVO_ART
    hvo_manual["imageType"] = "event_artwork"
    hvo_manual["imageOverride"] = True
    upsert(manual, hvo_manual)

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

    required_live = {f"manual:{event_id}" for event_id in EVENTBRITE_IDS} | {HVO_LIVE_ID, "manual:flavor-fest-2026-friday-concerts"}
    live_ids = {str(item.get("id")) for item in events}
    absent = sorted(required_live - live_ids)
    if absent:
        raise SystemExit(f"Verified live events missing after upsert: {absent}")

    rare_live = next((item for item in events if str(item.get("id")) == f"manual:{RARE_ID}"), None)
    if not rare_live or rare_live.get("status") != "cancelled" or not rare_live.get("cancellationConfirmed"):
        raise SystemExit("Confirmed Rare of Breed cancellation was not preserved")

    print("Verified Eventbrite discoveries, Flavor Fest Friday, HVO artwork, and confirmed cancellations are pinned in the live feed.")


if __name__ == "__main__":
    main()
