#!/usr/bin/env python3
"""Apply durable editorial decisions before collection/build.

This runs in CI after the full source test suite and before event collection/build.
It keeps non-CHH exclusions out of monitoring/output and injects manually verified
supplemental events that are not reliably discoverable from automated sources.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

POLICY_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"

EXCLUDED_ARTISTS = {"madison ryann ward"}

MIKE_TEEZY_HRVSTLAND = {
    "id": "mike-teezy-hrvstland-festival-2026",
    "title": "HRVSTLAND Festival 2026",
    "startDate": "2026-10-24",
    "startTime": "",
    "venue": "Steele Creek Church",
    "address": "",
    "city": "Charlotte",
    "state": "NC",
    "artists": ["Mike Teezy"],
    "headliner": "Mike Teezy",
    "eventType": "festival",
    "ticketUrl": "https://www.bandsintown.com/f/231374",
    "officialUrl": "https://www.bandsintown.com/f/231374",
    "image": "",
    "price": "",
    "status": "scheduled",
    "lineupExplicit": True,
    "authority": "artist_calendar",
    "sourceName": "Mike Teezy verified Bandsintown / HRVSTLAND listing",
}


def load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def curate_event(event: dict[str, Any]) -> dict[str, Any] | None:
    artists = [
        artist for artist in event.get("artists", [])
        if norm(artist) not in EXCLUDED_ARTISTS
    ]
    if not artists:
        return None

    updated = dict(event)
    updated["artists"] = artists
    if norm(updated.get("headliner")) in EXCLUDED_ARTISTS:
        updated["headliner"] = artists[0]
    return updated


def event_identity(event: dict[str, Any]) -> tuple[str, str, str]:
    return (
        norm(event.get("id")),
        str(event.get("startDate") or ""),
        norm(event.get("city")),
    )


def main() -> int:
    artists = load(ARTISTS_FILE)
    events = load(EVENTS_FILE)
    supplemental = load(SUPPLEMENTAL_FILE)

    if not isinstance(artists, list) or not isinstance(events, list) or not isinstance(supplemental, list):
        raise SystemExit("Curated catalog policy expected JSON arrays")

    found_madison = False
    for artist in artists:
        if not isinstance(artist, dict) or norm(artist.get("name")) != "madison ryann ward":
            continue
        found_madison = True
        artist["enabled"] = False
        artist["ticketmasterEnabled"] = False
        artist["socialSearchEnabled"] = False
        artist["textMatchEnabled"] = False
        artist["activeStatus"] = "excluded_non_chh"
        artist["editorialNote"] = "Excluded from Kingdom Circuit: not Christian hip-hop."

    if not found_madison:
        raise SystemExit("Madison Ryann Ward roster entry was not found")

    curated_events = []
    removed_events = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        curated = curate_event(event)
        if curated is None:
            removed_events += 1
            continue
        curated_events.append(curated)

    curated_supplemental = []
    for event in supplemental:
        if not isinstance(event, dict):
            continue
        curated = curate_event(event)
        if curated is not None:
            curated_supplemental.append(curated)

    target_id = norm(MIKE_TEEZY_HRVSTLAND["id"])
    curated_supplemental = [
        event for event in curated_supplemental
        if norm(event.get("id")) != target_id
    ]
    curated_supplemental.append(MIKE_TEEZY_HRVSTLAND)
    curated_supplemental.sort(key=lambda event: (str(event.get("startDate") or "9999-12-31"), norm(event.get("title"))))

    write(ARTISTS_FILE, artists)
    write(EVENTS_FILE, curated_events)
    write(SUPPLEMENTAL_FILE, curated_supplemental)

    enabled_names = {
        norm(artist.get("name"))
        for artist in artists
        if isinstance(artist, dict) and artist.get("enabled", True)
    }
    if "madison ryann ward" in enabled_names:
        raise SystemExit("Madison Ryann Ward is still enabled")

    all_published = [*curated_events, *curated_supplemental]
    if any("madison ryann ward" in {norm(name) for name in event.get("artists", [])} for event in all_published):
        raise SystemExit("Madison Ryann Ward still appears in published event data")

    if not any(norm(event.get("id")) == target_id for event in curated_supplemental):
        raise SystemExit("Mike Teezy HRVSTLAND event was not injected")

    print(
        f"Curated catalog policy v{POLICY_VERSION} applied: Madison Ryann Ward disabled; "
        f"{removed_events} Madison-only event(s) removed; "
        "Mike Teezy HRVSTLAND Festival 2026 ensured."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
