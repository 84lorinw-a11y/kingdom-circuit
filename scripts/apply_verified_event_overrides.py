#!/usr/bin/env python3
"""Apply durable, manually verified event fixes before every production build."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

PARRIS_EVENT = {
    "id": "manual:parris-chariz-dallas-2026-10-11",
    "title": "Parris Chariz — THE WORLD IS WATCHING LIVE",
    "startDate": "2026-10-11",
    "startTime": "20:30",
    "timezone": "America/Chicago",
    "venue": "AM/FM - Lounge",
    "address": "1950 Market Center Blvd",
    "city": "Dallas",
    "state": "TX",
    "country": "US",
    "artists": ["Parris Chariz", "Toschii", "Eli Montanna", "JWoodz"],
    "headliner": "Parris Chariz",
    "eventType": "concert",
    "status": "scheduled",
    "ticketUrl": "https://www.eventim.us/event/parris-chariz/699959",
    "officialUrl": "https://www.eventim.us/event/parris-chariz/699959",
    "image": "assets/artists/parris-chariz.webp",
    "imageType": "artist",
    "imagePosition": "center",
    "price": "",
    "sourceName": "Spune / Eventim official listing",
    "authority": "official_event",
    "confidence": "high",
    "lineupExplicit": True,
    "sources": [
        {
            "name": "Eventim official ticket listing",
            "url": "https://www.eventim.us/event/parris-chariz/699959",
            "type": "manual_verified",
            "authority": "venue_ticket",
            "priority": 112,
        },
        {
            "name": "Spune official show calendar",
            "url": "https://spune.com/shows/",
            "type": "manual_verified",
            "authority": "official_event",
            "priority": 100,
        },
    ],
}

KADEN_IMAGE = "https://images.sk-static.com/images/media/profile_images/artists/10314485/large_avatar"
KADEN_TOUR_URL = "https://kadenjordan.com/pages/tour"
KADEN_SONGKICK_URL = "https://www.songkick.com/artists/10314485-kaden-jordan"
KADEN_SHOWS = [
    ("2026-09-23", "Church in the Son", "Orlando", "FL"),
    ("2026-10-23", "Trinity College", "New Port Richey", "FL"),
    ("2026-11-13", "The Gathering Place", "Orlando", "FL"),
    ("2026-12-11", "NEXT CHURCH", "Ocala", "FL"),
]


def kaden_event(date: str, venue: str, city: str, state: str) -> dict:
    slug = f"{date}-{city.lower().replace(' ', '-')}"
    return {
        "id": f"manual:kaden-jordan-{slug}",
        "title": "Kaden Jordan Live",
        "startDate": date,
        "startTime": "",
        "timezone": "America/New_York",
        "venue": venue,
        "address": "",
        "city": city,
        "state": state,
        "country": "US",
        "artists": ["Kaden Jordan"],
        "headliner": "Kaden Jordan",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": KADEN_SONGKICK_URL,
        "officialUrl": KADEN_TOUR_URL,
        "image": KADEN_IMAGE,
        "imageType": "artist",
        "imagePosition": "center",
        "price": "",
        "sourceName": "Kaden Jordan official tour page / Songkick",
        "authority": "artist_calendar",
        "confidence": "high",
        "lineupExplicit": True,
        "sources": [
            {
                "name": "Kaden Jordan official TOUR page",
                "url": KADEN_TOUR_URL,
                "type": "manual_verified",
                "authority": "artist_calendar",
                "priority": 100,
            },
            {
                "name": "Songkick calendar linked by Kaden Jordan official site",
                "url": KADEN_SONGKICK_URL,
                "type": "manual_verified",
                "authority": "artist_calendar",
                "priority": 90,
            },
        ],
    }


def norm(value: object) -> str:
    return str(value or "").strip().casefold()


def load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Expected JSON array: {path}")
    return data


def write(path: Path, data: list[dict]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_parris_duplicate(event: dict) -> bool:
    date = str(event.get("startDate") or "")[:10]
    if date not in {"2026-10-11", "2026-10-12"}:
        return False
    if norm(event.get("city")) != "dallas":
        return False
    names = {norm(name) for name in event.get("artists", [])}
    parris = (
        "parris chariz" in names
        or norm(event.get("headliner")) == "parris chariz"
        or "parris chariz" in norm(event.get("title"))
    )
    return parris and (
        norm(event.get("address")) == "1950 market center blvd"
        or "world is watching" in norm(event.get("title"))
        or event.get("id") == "bandsintown:108802282"
    )


def is_same_kaden_show(event: dict, date: str, city: str) -> bool:
    if str(event.get("startDate") or "")[:10] != date:
        return False
    if norm(event.get("city")) != norm(city):
        return False
    names = {norm(name) for name in event.get("artists", [])}
    return "kaden jordan" in names or norm(event.get("headliner")) == "kaden jordan"


def sort_events(events: list[dict]) -> None:
    events.sort(key=lambda item: (
        str(item.get("startDate") or "9999-99-99"),
        str(item.get("startTime") or ""),
        str(item.get("title") or ""),
    ))


def apply(root: Path) -> None:
    events_path = root / "events.json"
    supplemental_path = root / "supplemental-events.json"
    events = load(events_path)
    supplemental = load(supplemental_path)

    events = [event for event in events if not is_parris_duplicate(event)]
    supplemental = [event for event in supplemental if not is_parris_duplicate(event)]

    for date, _venue, city, _state in KADEN_SHOWS:
        events = [event for event in events if not is_same_kaden_show(event, date, city)]
        supplemental = [event for event in supplemental if not is_same_kaden_show(event, date, city)]

    events.append(deepcopy(PARRIS_EVENT))
    events.extend(kaden_event(*show) for show in KADEN_SHOWS)
    sort_events(events)
    sort_events(supplemental)
    write(events_path, events)
    write(supplemental_path, supplemental)

    combined = events + supplemental
    parris = [event for event in combined if is_parris_duplicate(event)]
    if len(parris) != 1 or parris[0].get("id") != PARRIS_EVENT["id"]:
        raise SystemExit(f"Parris Dallas dedupe failed: {[event.get('id') for event in parris]}")
    if parris[0].get("artists") != PARRIS_EVENT["artists"]:
        raise SystemExit("Parris Dallas verified support lineup is missing")

    for date, venue, city, _state in KADEN_SHOWS:
        matches = [event for event in combined if is_same_kaden_show(event, date, city)]
        if len(matches) != 1 or matches[0].get("venue") != venue:
            raise SystemExit(f"Kaden Jordan show verification failed for {date} {city}: {matches}")

    print("Verified Parris Chariz Dallas lineup/dedupe and four Kaden Jordan tour dates are pinned.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=".", help="Repository or built-site root")
    args = parser.parse_args()
    apply(Path(args.source).resolve())


if __name__ == "__main__":
    main()
