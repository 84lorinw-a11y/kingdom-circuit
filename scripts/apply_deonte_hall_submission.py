#!/usr/bin/env python3
"""Keep Deonte Hall's verified artist record and submitted Battle Creek show live.

Source-of-truth inputs:
- Kingdom Circuit Artist Database verified row for Deonte Hall.
- Artist-submitted Kingdom Circuit show form, with the organizer's Facebook post
  supplied as the official event-details URL.

This guard runs on every production deployment so the verified artist record and
submitted show survive collector refreshes and roster rebuilds.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
VERIFIED_UPDATES_FILE = ROOT / "config" / "verified-artist-registry-updates.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"

ARTIST_NAME = "Deonte Hall"
SOURCE_ROSTER_ORDER = 111
FACEBOOK_EVENT_URL = "https://www.facebook.com/share/p/18y8svvmDm/?mibextid=wwXIfr"

ARTIST_RECORD: dict[str, Any] = {
    "name": ARTIST_NAME,
    "aliases": [ARTIST_NAME],
    "enabled": True,
    "ticketmasterEnabled": False,
    "category": "core",
    "monitoringPriority": 2,
    "topStreamingPriority": False,
    "socialSearchEnabled": True,
    "activeStatus": "active_or_unknown",
    "textMatchEnabled": False,
    "instagramProfile": "https://www.instagram.com/deontehall100/",
    "spotifyProfile": "https://open.spotify.com/artist/1o4z5bdBNIeJZGIHeseIhf",
    "youtubeProfile": "https://www.youtube.com/@deontehallofficial",
    "officialImageSource": "https://www.instagram.com/deontehall100/",
    "sourceRegistryVerified": True,
    "sourceRegistryRosterOrder": SOURCE_ROSTER_ORDER,
}

VERIFIED_UPDATE: dict[str, Any] = {
    "rosterOrder": SOURCE_ROSTER_ORDER,
    "name": ARTIST_NAME,
    "aliases": [ARTIST_NAME],
    "category": "core",
    "monitoringPriority": 2,
    "ticketmasterEnabled": False,
    "textMatchEnabled": False,
    "instagramProfile": "https://www.instagram.com/deontehall100/",
    "spotifyProfile": "https://open.spotify.com/artist/1o4z5bdBNIeJZGIHeseIhf",
    "youtubeProfile": "https://www.youtube.com/@deontehallofficial",
    "officialImageSource": "https://www.instagram.com/deontehall100/",
}

SUBMITTED_EVENT: dict[str, Any] = {
    "id": "submitted:deonte-hall-truth-in-action-battle-creek-2026",
    "title": "Truth in Action First Annual Gospel Music Concert",
    "startDate": "2026-09-12",
    "startTime": "18:00",
    "timezone": "America/Detroit",
    "venue": "First Presbyterian Church",
    "address": "",
    "city": "Battle Creek",
    "state": "MI",
    "country": "US",
    "artists": [ARTIST_NAME],
    "headliner": ARTIST_NAME,
    "eventType": "concert",
    "status": "scheduled",
    "ticketUrl": "",
    "officialUrl": FACEBOOK_EVENT_URL,
    "price": "",
    "sourceName": "Artist-submitted Kingdom Circuit listing",
    "authority": "artist_submission",
    "confidence": "high",
    "lineupExplicit": False,
    "sources": [
        {
            "name": "Deonte Hall submission to Kingdom Circuit",
            "url": FACEBOOK_EVENT_URL,
            "type": "artist_submission",
            "authority": "artist_submission",
            "priority": 100,
        }
    ],
}


def norm(value: object) -> str:
    return str(value or "").strip().casefold()


def load_array(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        value = []
    if not isinstance(value, list):
        raise SystemExit(f"Expected JSON array: {path}")
    return [item for item in value if isinstance(item, dict)]


def save_array(path: Path, value: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def patch_verified_updates() -> None:
    updates = load_array(VERIFIED_UPDATES_FILE)
    updates = [item for item in updates if norm(item.get("name")) != norm(ARTIST_NAME)]

    # Position 111 is intentionally between the verified Neisha Glow row and
    # the existing Alex Jean roster entry in the Artist Database ordering.
    if any(int(item.get("rosterOrder") or 0) == SOURCE_ROSTER_ORDER for item in updates):
        raise SystemExit(f"Verified registry roster position {SOURCE_ROSTER_ORDER} is already occupied")

    updates.append(dict(VERIFIED_UPDATE))
    updates.sort(key=lambda item: (int(item.get("rosterOrder") or 99999), norm(item.get("name"))))
    save_array(VERIFIED_UPDATES_FILE, updates)


def patch_artists() -> None:
    artists = load_array(ARTISTS_FILE)
    artists = [item for item in artists if norm(item.get("name")) != norm(ARTIST_NAME)]

    insert_at = min(max(SOURCE_ROSTER_ORDER - 1, 0), len(artists))
    artists.insert(insert_at, dict(ARTIST_RECORD))
    for index, artist in enumerate(artists, 1):
        artist["rosterOrder"] = index
    save_array(ARTISTS_FILE, artists)


def patch_submitted_event() -> None:
    supplemental = load_array(SUPPLEMENTAL_FILE)
    supplemental = [
        event for event in supplemental
        if str(event.get("id") or "") != SUBMITTED_EVENT["id"]
    ]
    supplemental.append(dict(SUBMITTED_EVENT))
    supplemental.sort(
        key=lambda event: (
            str(event.get("startDate") or "9999-12-31"),
            str(event.get("startTime") or ""),
            str(event.get("title") or ""),
        )
    )
    save_array(SUPPLEMENTAL_FILE, supplemental)


def verify() -> None:
    artists = load_array(ARTISTS_FILE)
    matches = [item for item in artists if norm(item.get("name")) == norm(ARTIST_NAME)]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one {ARTIST_NAME} artist record, found {len(matches)}")
    artist = matches[0]
    if int(artist.get("rosterOrder") or 0) != SOURCE_ROSTER_ORDER:
        raise SystemExit(f"{ARTIST_NAME} roster order is wrong: {artist.get('rosterOrder')}")
    for field in ("instagramProfile", "spotifyProfile", "youtubeProfile"):
        if artist.get(field) != ARTIST_RECORD[field]:
            raise SystemExit(f"{ARTIST_NAME} verified {field} did not persist")

    supplemental = load_array(SUPPLEMENTAL_FILE)
    shows = [event for event in supplemental if str(event.get("id") or "") == SUBMITTED_EVENT["id"]]
    if len(shows) != 1:
        raise SystemExit(f"Expected exactly one submitted Deonte Hall event, found {len(shows)}")
    show = shows[0]
    required = {
        "startDate": "2026-09-12",
        "startTime": "18:00",
        "venue": "First Presbyterian Church",
        "city": "Battle Creek",
        "state": "MI",
    }
    for field, expected in required.items():
        if show.get(field) != expected:
            raise SystemExit(f"Deonte Hall event {field} mismatch: {show.get(field)!r}")


def main() -> int:
    patch_verified_updates()
    patch_artists()
    patch_submitted_event()
    verify()
    print("Deonte Hall verified artist record and submitted Battle Creek show applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
