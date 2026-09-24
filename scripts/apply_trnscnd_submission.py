#!/usr/bin/env python3
"""Keep the promoter-submitted [TRNSCND] VA 2026 event live and complete."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANUAL_EVENTS_FILE = ROOT / "config" / "manual-events.json"
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
UPDATES_FILE = ROOT / "config" / "verified-artist-registry-updates.json"
SYNC_ARTISTS = ROOT / "scripts" / "sync_verified_artist_registry.py"

EVENT_ID = "trnscnd-va-fredericksburg-2026"
RUNTIME_EVENT_ID = f"manual:{EVENT_ID}"
OFFICIAL_URL = "https://othrwrldly.com/trnscnd"
ARTWORK_SOURCE_URL = (
    "https://drive.google.com/file/d/"
    "1dB8NPwMCpGh7I9RYOQ6j0lzz1qTsYKB7/view?usp=drivesdk"
)
ARTWORK_URL = (
    "https://drive.google.com/thumbnail?"
    "id=1dB8NPwMCpGh7I9RYOQ6j0lzz1qTsYKB7&sz=w1600"
)

PROFILED_ARTISTS = ["N!X", "NXTMIKE", "D Riddick", "Howard Langford"]
FULL_LINEUP = [
    "N!X",
    "NXTMIKE",
    "D Riddick",
    "Howard Langford",
    "Leah Dates",
    "Rolanda Carter",
    "DJ Smalls",
]

# NXTMIKE is already the verified registry's row 146. These three are the next
# rows supplied by the site owner from the canonical artist database. Links are
# deliberately left pending rather than guessed from ambiguous search results.
NEW_ARTISTS = [
    {
        "rosterOrder": 178,
        "name": "N!X",
        "aliases": ["N!X"],
        "category": "core",
        "monitoringPriority": 3,
        "ticketmasterEnabled": False,
        "textMatchEnabled": False,
        "imagePosition": "center",
    },
    {
        "rosterOrder": 179,
        "name": "D Riddick",
        "aliases": ["D Riddick", "D. Riddick"],
        "category": "core",
        "monitoringPriority": 3,
        "ticketmasterEnabled": False,
        "textMatchEnabled": True,
        "website": "https://unitedmasters.com/a/d-riddick",
        "officialImageSource": "https://unitedmasters.com/a/d-riddick",
        "imagePosition": "center",
    },
    {
        "rosterOrder": 180,
        "name": "Howard Langford",
        "aliases": ["Howard Langford"],
        "category": "core",
        "monitoringPriority": 3,
        "ticketmasterEnabled": False,
        "textMatchEnabled": True,
        "imagePosition": "center",
    },
]

EVENT = {
    "id": EVENT_ID,
    "title": "[TRNSCND] VA 2026",
    "startDate": "2026-11-14",
    "endDate": "2026-11-14",
    "startTime": "16:30",
    "endTime": "20:00",
    "timezone": "America/New_York",
    "venue": "Calvary Chapel Fredericksburg",
    "address": "3625 Latimers Knoll Ct",
    "postalCode": "22408",
    "city": "Fredericksburg",
    "state": "VA",
    "country": "US",
    # Only artists confirmed in the owner's artist database are linked to
    # profiles. The entire submitted bill remains visible via advertisedBilling.
    "artists": PROFILED_ARTISTS,
    "advertisedBilling": FULL_LINEUP,
    "officialBill": FULL_LINEUP,
    "headliner": "N!X",
    "supportActs": FULL_LINEUP[1:],
    "eventType": "concert",
    "status": "scheduled",
    "ticketUrl": OFFICIAL_URL,
    "officialUrl": OFFICIAL_URL,
    "image": ARTWORK_URL,
    "imageType": "event_artwork",
    "imagePosition": "center",
    "imageOverride": True,
    "imageSource": "Promoter-supplied official [TRNSCND] VA 2026 artwork",
    "imageSourceUrl": ARTWORK_SOURCE_URL,
    "price": "$15 concert pass / $20 full-day pass",
    "organizer": "OTHRWRLDLY.",
    "sourceName": "Promoter submission and OTHRWRLDLY official event page",
    "authority": "promoter_submission",
    "confidence": "high",
    "lineupExplicit": True,
    "firstSeen": "2026-09-24T12:00:00Z",
    "lastVerified": "2026-09-24T12:00:00Z",
    "auditVerified": "2026-09-24",
    "notes": (
        "Promoter Shawn Mitchell submitted the complete performance lineup. "
        "The organizer's official page confirms the date, 4:30–8:00 PM time "
        "span, venue address, and ticket options."
    ),
    "sources": [
        {
            "name": "OTHRWRLDLY official [TRNSCND] 2026 event page",
            "url": OFFICIAL_URL,
            "type": "official_event",
            "authority": "official_event",
            "priority": 112,
        },
        {
            "name": "Kingdom Circuit promoter submission from Shawn Mitchell",
            "url": OFFICIAL_URL,
            "type": "promoter_submission",
            "authority": "promoter_submission",
            "priority": 110,
        },
        {
            "name": "Promoter-supplied official event artwork",
            "url": ARTWORK_SOURCE_URL,
            "type": "promoter_submission",
            "authority": "promoter_submission",
            "priority": 110,
        },
    ],
}


def norm(value: object) -> str:
    return str(value or "").strip().casefold()


def load_array(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise SystemExit(f"Expected a JSON array: {path}")
    return [item for item in value if isinstance(item, dict)]


def write_array(path: Path, rows: list[dict]) -> None:
    path.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def event_collision(event: dict) -> bool:
    event_id = str(event.get("id") or "").removeprefix("manual:")
    if event_id == EVENT_ID:
        return True
    return (
        str(event.get("startDate") or "")[:10] == EVENT["startDate"]
        and norm(event.get("city")) == norm(EVENT["city"])
        and "trnscnd" in norm(event.get("title"))
    )


def patch_artist_registry() -> None:
    updates = load_array(UPDATES_FILE)
    new_names = {norm(row["name"]) for row in NEW_ARTISTS}
    updates = [row for row in updates if norm(row.get("name")) not in new_names]
    occupied = {
        int(row.get("rosterOrder") or 0): str(row.get("name") or "")
        for row in updates
    }
    for row in NEW_ARTISTS:
        order = int(row["rosterOrder"])
        if order in occupied:
            raise SystemExit(
                f"Artist database row {order} is already occupied by {occupied[order]}"
            )
        updates.append(deepcopy(row))
    updates.sort(key=lambda row: int(row.get("rosterOrder") or 99999))
    write_array(UPDATES_FILE, updates)
    subprocess.run([sys.executable, str(SYNC_ARTISTS)], cwd=ROOT, check=True)


def patch_events() -> None:
    manual = [row for row in load_array(MANUAL_EVENTS_FILE) if not event_collision(row)]
    manual.append(deepcopy(EVENT))
    manual.sort(
        key=lambda row: (
            str(row.get("startDate") or "9999-12-31"),
            str(row.get("startTime") or ""),
            str(row.get("title") or ""),
        )
    )
    write_array(MANUAL_EVENTS_FILE, manual)

    runtime_event = deepcopy(EVENT)
    runtime_event["id"] = RUNTIME_EVENT_ID
    events = [row for row in load_array(EVENTS_FILE) if not event_collision(row)]
    events.append(runtime_event)
    events.sort(
        key=lambda row: (
            str(row.get("startDate") or "9999-12-31"),
            str(row.get("startTime") or ""),
            str(row.get("title") or ""),
        )
    )
    write_array(EVENTS_FILE, events)

    supplemental = [
        row for row in load_array(SUPPLEMENTAL_FILE) if not event_collision(row)
    ]
    write_array(SUPPLEMENTAL_FILE, supplemental)


def verify() -> None:
    manual = [row for row in load_array(MANUAL_EVENTS_FILE) if event_collision(row)]
    events = [row for row in load_array(EVENTS_FILE) if event_collision(row)]
    supplemental = [
        row for row in load_array(SUPPLEMENTAL_FILE) if event_collision(row)
    ]
    if [row.get("id") for row in manual] != [EVENT_ID]:
        raise SystemExit(f"Unexpected manual [TRNSCND] records: {manual}")
    if [row.get("id") for row in events] != [RUNTIME_EVENT_ID]:
        raise SystemExit(f"Unexpected runtime [TRNSCND] records: {events}")
    if supplemental:
        raise SystemExit(f"Duplicate supplemental [TRNSCND] records remain: {supplemental}")
    event = events[0]
    for field in (
        "startDate",
        "startTime",
        "endTime",
        "venue",
        "address",
        "postalCode",
        "city",
        "state",
        "artists",
        "advertisedBilling",
        "officialUrl",
        "image",
    ):
        if event.get(field) != EVENT[field]:
            raise SystemExit(f"[TRNSCND] {field} mismatch: {event.get(field)!r}")

    artist_names = {norm(row.get("name")) for row in load_array(ROOT / "config" / "artists.json")}
    missing = [name for name in PROFILED_ARTISTS if norm(name) not in artist_names]
    if missing:
        raise SystemExit(f"[TRNSCND] profiled artists are missing: {missing}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    patch_artist_registry()
    patch_events()
    verify()
    print("[TRNSCND] VA 2026 submission and artist directory records are pinned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
