#!/usr/bin/env python3
"""Durable verified repairs for Miles Minnick and CJ Emulous fall 2026 shows."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DATE = "2026-09-23"
ARTISTS = ["Miles Minnick", "Tommy Zuko", "CJ Emulous"]
MILES_IMAGE = "assets/artists/miles-minnick.webp"


def source(name: str, url: str, authority: str, priority: int) -> dict:
    return {
        "name": name,
        "url": url,
        "type": "manual_verified",
        "authority": authority,
        "priority": priority,
    }


CANONICAL_EVENTS = {
    "miles-minnick-black-box-north-miami-2026-11-05": {
        "title": "Miles Minnick at Black Box Media Miami",
        "startDate": "2026-11-05",
        "startTime": "18:30",
        "timezone": "America/New_York",
        "venue": "Black Box Media Miami",
        "address": "12355 NE 13th Ave Unit #403-404",
        "city": "North Miami",
        "state": "FL",
        "country": "US",
        "artists": ARTISTS,
        "headliner": "Miles Minnick",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.bandsintown.com/t/108940329",
        "officialUrl": "https://www.bandsintown.com/e/108940329-miles-minnick-at-black-box-media-miami",
        "image": MILES_IMAGE,
        "imageType": "artist",
        "imagePosition": "center",
        "lineupExplicit": True,
        "advertisedBilling": ARTISTS,
        "authority": "artist_calendar",
        "confidence": "high",
        "sourceName": "Bandsintown verified event listing",
        "sources": [
            source("Bandsintown verified event listing", "https://www.bandsintown.com/e/108940329-miles-minnick-at-black-box-media-miami", "artist_calendar", 94),
            source("CJ Emulous official tour calendar", "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-23", "artist_calendar", 88),
        ],
        "notes": "The venue-specific listing supersedes the older generic Miami placeholder. The published event time is 6:30 PM; CJ's earlier calendar entry displayed 6:00 PM without a venue.",
        "auditVerified": AUDIT_DATE,
    },
    "miles-minnick-christlike-university-jacksonville-2026-11-07": {
        "title": "Miles Minnick – Christlike University – Florida Campus Tour in Jacksonville",
        "startDate": "2026-11-07",
        "startTime": "19:00",
        "timezone": "America/New_York",
        "venue": "The Albatross",
        "venueAliases": ["Underbelly"],
        "address": "113 E Bay St",
        "city": "Jacksonville",
        "state": "FL",
        "country": "US",
        "artists": ARTISTS,
        "headliner": "Miles Minnick",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.livenation.com/event/rZ7HnEZ1AfGUq7/miles-minnick-christlike-university-florida-campus-tour-in-jacksonville",
        "officialUrl": "https://www.livenation.com/event/rZ7HnEZ1AfGUq7/miles-minnick-christlike-university-florida-campus-tour-in-jacksonville",
        "image": MILES_IMAGE,
        "imageType": "artist",
        "imagePosition": "center",
        "lineupExplicit": True,
        "advertisedBilling": ARTISTS,
        "authority": "venue_ticket",
        "confidence": "high",
        "sourceName": "Live Nation official event listing",
        "sources": [
            source("Live Nation official event listing", "https://www.livenation.com/event/rZ7HnEZ1AfGUq7/miles-minnick-christlike-university-florida-campus-tour-in-jacksonville", "venue_ticket", 112),
            source("Bandsintown verified lineup", "https://www.bandsintown.com/e/108940352-miles-minnick-at-the-albatross", "artist_calendar", 94),
        ],
        "supersededSources": [
            {
                "url": "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-25",
                "publishedDate": "2026-11-07",
                "publishedCity": "Tampa",
                "reason": "Conflicts with the venue-specific Jacksonville ticket listing and is not supported by the official Flavor Fest concert schedule.",
            }
        ],
        "notes": "The venue-specific Jacksonville ticket listing supersedes CJ's older November 7 Tampa calendar entry. Miles may also appear on the 11:45 AM Flavor Fest artist panel in Tampa; that daytime panel is not this concert.",
        "auditVerified": AUDIT_DATE,
    },
    "miles-minnick-christlike-university-orlando-2026-11-08": {
        "title": "Miles Minnick – Christlike University – Florida Campus Tour in Orlando",
        "startDate": "2026-11-08",
        "startTime": "19:00",
        "timezone": "America/New_York",
        "venue": "Conduit",
        "address": "6700 Aloma Ave",
        "city": "Winter Park",
        "advertisedCity": "Orlando",
        "state": "FL",
        "country": "US",
        "artists": ARTISTS,
        "headliner": "Miles Minnick",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.livenation.com/event/rZ7HnEZ1AfGUq0/miles-minnick-christlike-university-florida-campus-tour-in-orlando",
        "officialUrl": "https://www.livenation.com/event/rZ7HnEZ1AfGUq0/miles-minnick-christlike-university-florida-campus-tour-in-orlando",
        "image": MILES_IMAGE,
        "imageType": "artist",
        "imagePosition": "center",
        "lineupExplicit": True,
        "advertisedBilling": ARTISTS,
        "authority": "venue_ticket",
        "confidence": "high",
        "sourceName": "Live Nation official event listing",
        "sources": [
            source("Live Nation official event listing", "https://www.livenation.com/event/rZ7HnEZ1AfGUq0/miles-minnick-christlike-university-florida-campus-tour-in-orlando", "venue_ticket", 112),
            source("Bandsintown verified lineup", "https://www.bandsintown.com/e/108940372-miles-minnick-at-conduit", "artist_calendar", 94),
        ],
        "supersededSources": [
            {
                "url": "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-26",
                "publishedDate": "2026-11-08",
                "publishedCity": "Jacksonville",
                "reason": "Conflicts with the venue-specific Conduit ticket listing in Winter Park.",
            }
        ],
        "notes": "The ticket listing advertises Orlando, but Conduit's physical address is in Winter Park. This supersedes CJ's older generic November 8 Jacksonville entry.",
        "auditVerified": AUDIT_DATE,
    },
}


OLD_MANUAL_IDS = {
    "cj-emulous-new-mainstream-miami-2026-11-05": "miles-minnick-black-box-north-miami-2026-11-05",
    "cj-emulous-new-mainstream-jacksonville-2026-11-08": "miles-minnick-christlike-university-orlando-2026-11-08",
}

BANDSINTOWN_REDIRECTS = {
    "bandsintown:108940329": (
        "Miles Minnick at Black Box Media Miami",
        "2026-11-05",
        "North Miami",
        "miles-minnick-black-box-north-miami-2026-11-05",
    ),
    "bandsintown:108940352": (
        "Miles Minnick at The Albatross",
        "2026-11-07",
        "Jacksonville",
        "miles-minnick-christlike-university-jacksonville-2026-11-07",
    ),
    "bandsintown:108940372": (
        "Miles Minnick at Conduit",
        "2026-11-08",
        "Winter Park",
        "miles-minnick-christlike-university-orlando-2026-11-08",
    ),
}

TIME_REPAIRS = {
    "cj-emulous-glo-concert-los-angeles-2026": "18:00",
    "cj-emulous-christlike-christmas-berkeley-2026": "18:00",
    "cj-emulous-christlike-christmas-felton-2026": "19:00",
    "miles-cj-zion-ultra-lounge-chandler-2026": "19:00",
}

TIME_NOTES = {
    "cj-emulous-glo-concert-los-angeles-2026": "CJ Emulous's official calendar confirms Los Angeles on November 15, 2026 at 6:00 PM. Venue and additional artists remain unconfirmed.",
    "cj-emulous-christlike-christmas-berkeley-2026": "CJ Emulous's official calendar confirms Berkeley on December 2, 2026 at 6:00 PM. Venue remains unpublished.",
    "cj-emulous-christlike-christmas-felton-2026": "CJ Emulous's official calendar confirms Felton on December 4, 2026 at 7:00 PM. Venue remains unpublished.",
    "miles-cj-zion-ultra-lounge-chandler-2026": "CJ Emulous's official calendar confirms Miles Minnick and CJ Emulous at Zion Ultra Lounge on December 5, 2026 at 7:00 PM.",
}


def read(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def bare_id(value: object) -> str:
    return str(value or "").removeprefix("manual:")


def apply_manual_source() -> None:
    path = ROOT / "config" / "manual-events.json"
    rows = read(path)
    managed = set(CANONICAL_EVENTS) | set(OLD_MANUAL_IDS)
    rows = [row for row in rows if bare_id(row.get("id")) not in managed]
    for event_id, event in CANONICAL_EVENTS.items():
        rows.append({**event, "id": event_id})
    for row in rows:
        identity = bare_id(row.get("id"))
        if identity in TIME_REPAIRS:
            row["startTime"] = TIME_REPAIRS[identity]
            row["notes"] = TIME_NOTES[identity]
            row["auditVerified"] = AUDIT_DATE
    write(path, rows)


def merged_record(event_id: str, title: str, date: str, city: str, state: str, target: str) -> dict:
    return {
        "id": event_id,
        "title": title,
        "startDate": date,
        "startTime": "",
        "timezone": "America/New_York",
        "venue": "Venue not provided",
        "address": "",
        "city": city,
        "state": state,
        "country": "US",
        "artists": ARTISTS,
        "headliner": "Miles Minnick",
        "eventType": "concert",
        "status": "merged",
        "mergedIntoId": f"manual:{target}",
        "officialUrl": "",
        "ticketUrl": "",
        "sourceName": "Superseded listing",
        "notes": "This older listing is retained only to redirect visitors to the corrected canonical event.",
        "auditVerified": AUDIT_DATE,
    }


def apply_runtime_events() -> None:
    path = ROOT / "events.json"
    rows = read(path)
    managed = (
        {f"manual:{event_id}" for event_id in CANONICAL_EVENTS}
        | {f"manual:{event_id}" for event_id in OLD_MANUAL_IDS}
        | set(BANDSINTOWN_REDIRECTS)
    )
    rows = [row for row in rows if str(row.get("id") or "") not in managed]
    for event_id, event in CANONICAL_EVENTS.items():
        rows.append({**event, "id": f"manual:{event_id}"})

    old_shapes = {
        "cj-emulous-new-mainstream-miami-2026-11-05": ("New Mainstream Tour — Miles Minnick, Tommy Zuko & CJ Emulous", "2026-11-05", "Miami", "FL"),
        "cj-emulous-new-mainstream-jacksonville-2026-11-08": ("New Mainstream Tour — Miles Minnick, Tommy Zuko & CJ Emulous", "2026-11-08", "Jacksonville", "FL"),
    }
    for old_id, target in OLD_MANUAL_IDS.items():
        title, date, city, state = old_shapes[old_id]
        rows.append(merged_record(f"manual:{old_id}", title, date, city, state, target))
    for old_id, (title, date, city, target) in BANDSINTOWN_REDIRECTS.items():
        rows.append(merged_record(old_id, title, date, city, "FL", target))

    for row in rows:
        identity = bare_id(row.get("id"))
        if identity in TIME_REPAIRS:
            row["startTime"] = TIME_REPAIRS[identity]
            row["notes"] = TIME_NOTES[identity]
            row["auditVerified"] = AUDIT_DATE
    write(path, rows)


def apply_supplemental_support() -> None:
    path = ROOT / "supplemental-events.json"
    rows = read(path)
    for row in rows:
        event_id = str(row.get("id") or "")
        if event_id in BANDSINTOWN_REDIRECTS:
            row["artists"] = ARTISTS
            row["lineupExplicit"] = True
            row["advertisedBilling"] = ARTISTS
            row["auditVerified"] = AUDIT_DATE
        identity = bare_id(event_id)
        if identity in TIME_REPAIRS:
            row["startTime"] = TIME_REPAIRS[identity]
            row["notes"] = TIME_NOTES[identity]
            row["auditVerified"] = AUDIT_DATE
    write(path, rows)


def apply_artist_alias() -> None:
    path = ROOT / "config" / "artists.json"
    rows = read(path)
    artist = next(row for row in rows if str(row.get("name") or "").casefold() == "cj emulous")
    aliases = list(dict.fromkeys([*(artist.get("aliases") or []), "CJ Emulous GLO.", "CJ Emulous GLO"]))
    artist["aliases"] = aliases
    write(path, rows)


def verify() -> None:
    events = read(ROOT / "events.json")
    active = [row for row in events if str(row.get("status") or "scheduled").casefold() == "scheduled"]
    by_id = {str(row.get("id") or ""): row for row in events}
    for event_id, expected in CANONICAL_EVENTS.items():
        row = by_id.get(f"manual:{event_id}")
        if row is None:
            raise SystemExit(f"Missing canonical event: {event_id}")
        for field in ("startDate", "startTime", "venue", "city", "state", "artists"):
            if row.get(field) != expected.get(field):
                raise SystemExit(f"Canonical event mismatch: {event_id}:{field}")
    stale = [
        row for row in active
        if row.get("startDate") in {"2026-11-07", "2026-11-08"}
        and row.get("state") == "FL"
        and row.get("city") in {"Tampa", "Jacksonville"}
        and "CJ Emulous" in (row.get("artists") or [])
        and str(row.get("id") or "") not in {"manual:miles-minnick-christlike-university-jacksonville-2026-11-07"}
    ]
    if stale:
        raise SystemExit(f"Stale CJ Florida records remain active: {[row.get('id') for row in stale]}")
    cj = next(row for row in read(ROOT / "config" / "artists.json") if row.get("name") == "CJ Emulous")
    if "CJ Emulous GLO." not in (cj.get("aliases") or []):
        raise SystemExit("CJ Emulous GLO. alias missing")


def main() -> None:
    apply_manual_source()
    apply_runtime_events()
    apply_supplemental_support()
    apply_artist_alias()
    verify()
    print("Verified Miles Minnick and CJ Emulous fall 2026 repairs applied.")


if __name__ == "__main__":
    main()
