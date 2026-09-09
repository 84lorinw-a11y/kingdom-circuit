#!/usr/bin/env python3
"""Keep Deonte Hall's verified artist record and submitted Battle Creek show live."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
VERIFIED_UPDATES_FILE = ROOT / "config" / "verified-artist-registry-updates.json"
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"

ARTIST_NAME = "Deonte Hall"
SOURCE_ROSTER_ORDER = 110
FACEBOOK_EVENT_URL = "https://www.facebook.com/deonte.hall.98832/photos/-battle-creek-michigan-im-coming-im-super-thankful-and-humbled-to-announce-that-/2995157700824677/"
FACEBOOK_ARTWORK_SOURCE = FACEBOOK_EVENT_URL
FACEBOOK_ARTWORK_URL = "assets/events/deonte-hall-truth-in-action-2026.webp"
OFFICIAL_WEBSITE = "https://deontehall.com/"
OFFICIAL_IMAGE_SOURCE = "https://deontehall.com/index.php/about-deonte/"
ARTIST_IMAGE = "https://deontehall.com/wp-content/uploads/2017/11/IMG_2799-1.jpg"

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
    "website": OFFICIAL_WEBSITE,
    "instagramProfile": "https://www.instagram.com/deontehall100/",
    "spotifyProfile": "https://open.spotify.com/artist/1o4z5bdBNIeJZGIHeseIhf",
    "youtubeProfile": "https://www.youtube.com/@deontehallofficial",
    "officialImageSource": OFFICIAL_IMAGE_SOURCE,
    "imageUrl": ARTIST_IMAGE,
    "imagePosition": "center",
    "preferArtistImage": True,
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
    "website": OFFICIAL_WEBSITE,
    "instagramProfile": "https://www.instagram.com/deontehall100/",
    "spotifyProfile": "https://open.spotify.com/artist/1o4z5bdBNIeJZGIHeseIhf",
    "youtubeProfile": "https://www.youtube.com/@deontehallofficial",
    "officialImageSource": OFFICIAL_IMAGE_SOURCE,
    "imageUrl": ARTIST_IMAGE,
    "imagePosition": "center",
    "preferArtistImage": True,
}

SUBMITTED_EVENT: dict[str, Any] = {
    "id": "submitted:deonte-hall-truth-in-action-battle-creek-2026",
    "title": "Truth in Action First Annual Gospel Music Concert",
    "startDate": "2026-09-12",
    "startTime": "18:00",
    "timezone": "America/Detroit",
    "venue": "First Presbyterian Church",
    "address": "111 Capital Ave NE",
    "city": "Battle Creek",
    "state": "MI",
    "country": "US",
    "artists": [ARTIST_NAME],
    "headliner": ARTIST_NAME,
    "eventType": "concert",
    "status": "scheduled",
    "ticketUrl": "",
    "officialUrl": FACEBOOK_EVENT_URL,
    "image": FACEBOOK_ARTWORK_URL,
    "imageType": "event_artwork",
    "imagePosition": "center",
    "imageOverride": True,
    "imageSource": FACEBOOK_ARTWORK_SOURCE,
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
        },
        {
            "name": "Deonte Hall supplied event artwork",
            "url": FACEBOOK_ARTWORK_SOURCE,
            "type": "manual_verified",
            "authority": "artist_submission",
            "priority": 100,
        },
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


def is_submitted_show_collision(event: dict[str, Any]) -> bool:
    if str(event.get("startDate") or "") != SUBMITTED_EVENT["startDate"]:
        return False
    if norm(event.get("city")) != "battle creek":
        return False
    event_artists = {norm(name) for name in event.get("artists", [])}
    return (
        norm(event.get("title")) == norm(SUBMITTED_EVENT["title"])
        or norm(ARTIST_NAME) in event_artists
    )


def patch_verified_updates() -> None:
    updates = load_array(VERIFIED_UPDATES_FILE)
    updates = [item for item in updates if norm(item.get("name")) != norm(ARTIST_NAME)]
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
    events = load_array(EVENTS_FILE)
    events = [event for event in events if not is_submitted_show_collision(event)]
    save_array(EVENTS_FILE, events)

    supplemental = load_array(SUPPLEMENTAL_FILE)
    supplemental = [
        event for event in supplemental
        if str(event.get("id") or "") != SUBMITTED_EVENT["id"]
        and not is_submitted_show_collision(event)
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
    for field in ("website", "instagramProfile", "spotifyProfile", "youtubeProfile", "imageUrl"):
        if artist.get(field) != ARTIST_RECORD[field]:
            raise SystemExit(f"{ARTIST_NAME} verified {field} did not persist")

    events = load_array(EVENTS_FILE)
    collisions = [event for event in events if is_submitted_show_collision(event)]
    if collisions:
        raise SystemExit(f"Collected duplicate Deonte Hall event still present: {collisions}")

    supplemental = load_array(SUPPLEMENTAL_FILE)
    shows = [event for event in supplemental if str(event.get("id") or "") == SUBMITTED_EVENT["id"]]
    if len(shows) != 1:
        raise SystemExit(f"Expected exactly one submitted Deonte Hall event, found {len(shows)}")
    show = shows[0]
    required = {
        "startDate": "2026-09-12",
        "startTime": "18:00",
        "venue": "First Presbyterian Church",
        "address": "111 Capital Ave NE",
        "city": "Battle Creek",
        "state": "MI",
        "officialUrl": FACEBOOK_EVENT_URL,
        "image": FACEBOOK_ARTWORK_URL,
        "imageType": "event_artwork",
        "imageSource": FACEBOOK_ARTWORK_SOURCE,
    }
    for field, expected in required.items():
        if show.get(field) != expected:
            raise SystemExit(f"Deonte Hall event {field} mismatch: {show.get(field)!r}")


def main() -> int:
    patch_verified_updates()
    patch_artists()
    patch_submitted_event()
    verify()
    print("Deonte Hall direct Facebook details and supplied event flyer applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
