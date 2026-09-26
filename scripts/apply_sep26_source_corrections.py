#!/usr/bin/env python3
"""Preserve reviewed concert starts, the Oasis reschedule and one Cleveland listing."""
from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from apply_sep13_content_repairs import NEW_EVENTS
from apply_sep13_requested_events import UPSERTS

ROOT = Path(__file__).resolve().parents[1]
DOVE_EVENT_ID = "bandsintown:1040305060"
DOVE_ARTWORK = {
    "image": "assets/events/dove-awards-2026-10-06.jpg",
    "imageType": "event_artwork", "imagePosition": "center", "imageOverride": True,
    "imageSource": "Bridgestone Arena official 57th Annual GMA Dove Awards artwork",
    "imageSourceUrl": "https://www.bridgestonearena.com/events/detail/57th-annual-gma-dove-awards",
}
OASIS_ID = "oasis-ministry-qbelv-new-york-2026"
MIAMI_ID = "mike-malagies-florida-takeover-miami-2026"
CLEVELAND_ID = "ticketmaster:vv1AAZk3FGkdmpCG1"
CLEVELAND_URL = "https://www.ticketmaster.com/beyond-the-walls-3-cleveland-ohio-11-07-2026/event/05006488EE58E30A"
CLEVELAND_POST = "https://www.instagram.com/p/DbwTgsNRsyI/"
RETIRED_IDS = {"official:4e2fc5c7c02ab1d34b9e", "supplemental:beyond-the-walls-3-brenno-2026", "bandsintown:108631622"}
RETIRED_URLS = {
    "https://music.apple.com/us/concerts/ce.01a1c61a-49a9-4e19-b629-46bac43b4970",
    "https://www.bandsintown.com/e/108631622",
}
CLEVELAND = {
    "id": CLEVELAND_ID, "title": "Beyond The Walls 3",
    "startDate": "2026-11-07", "startTime": "20:00", "doorsTime": "19:30",
    "startDateTime": "2026-11-07T20:00:00-05:00", "timezone": "America/New_York",
    "venue": "The Cambridge Room at House of Blues Cleveland", "address": "308 Euclid Ave",
    "city": "Cleveland", "state": "OH", "country": "US",
    "artists": ["KB", "Brenno", "Mike Teezy", "Porsha Love"], "headliner": "KB",
    "advertisedBilling": ["KB", "Brenno", "Mike Teezy", "Porsha Love", "Taylor Wells", "Renzoe"],
    "officialBill": ["KB", "Brenno", "Mike Teezy", "Porsha Love", "Taylor Wells", "Renzoe"],
    "eventType": "concert", "status": "scheduled", "lineupExplicit": True,
    "officialUrl": CLEVELAND_URL, "ticketUrl": CLEVELAND_URL,
    "image": "assets/events/beyond-the-walls-cleveland-2026-11-07.jpg",
    "imageType": "event_artwork", "imagePosition": "center", "imageOverride": True,
    "imageSource": "Promoter's official Beyond The Walls Cleveland flyer",
    "imageSourceUrl": CLEVELAND_POST,
    "firstSeen": "2026-07-30T03:46:47Z", "auditVerified": "2026-09-26",
    "confidence": "high", "authority": "venue_ticket", "sourceName": "Ticketmaster / House of Blues Cleveland",
    "sources": [{"name": "Ticketmaster / House of Blues Cleveland", "url": CLEVELAND_URL,
                 "type": "manual_verified", "authority": "venue_ticket", "priority": 112},
                {"name": "Beyond The Walls promoter's official flyer", "url": CLEVELAND_POST,
                 "type": "manual_verified", "authority": "organizer", "priority": 115}],
    "legacyEventPaths": ["/event/beyond-the-walls-2026-11-07-cleveland-91b8a7/"],
    "legacyEventNotice": "The Cleveland listings have been combined using the venue’s current concert details. Music starts at 8:00 PM on November 7.",
    "mergedFromIds": sorted(RETIRED_IDS),
    "notes": "Promoter submission and the official Eric Stephens / Beyond The Walls Instagram flyer confirm KB, Brenno, Mike Teezy, Porsha Love, Taylor Wells and Renzoe. This resolves the earlier incomplete Ticketmaster bill. Flyer explicitly dates November 7, 2026 and labels 6 PM VIP entry / 7:30 PM GA doors; Ticketmaster confirms music at 8 PM. Retain its official title Beyond The Walls 3 rather than the submission's conflicting 2027 title. Taylor Wells and Renzoe remain visible unlinked billing because they are outside the curated roster.",
    "sourceConflicts": [{"url": url, "reportedArtist": "Mike Teezy", "reportedStartTime": "18:00",
                         "resolution": "Promoter submission and official flyer confirm Mike Teezy on the canonical event. Keep the duplicate merged; 6 PM is VIP entry on the flyer, and Ticketmaster confirms the 8 PM concert start.",
                         "resolvedBy": CLEVELAND_POST, "resolvedDate": "2026-09-26"}
                        for url in sorted(RETIRED_URLS)],
}


def urls(row: dict) -> set[str]:
    return {str(row.get(key) or "").split("?")[0].rstrip("/") for key in ("officialUrl", "ticketUrl")}


def identity(row: dict) -> str | None:
    value = str(row.get("id") or "").removeprefix("manual:")
    if value in {OASIS_ID, MIAMI_ID}:
        return value
    if value == CLEVELAND_ID or value in RETIRED_IDS:
        return CLEVELAND_ID
    links = urls(row)
    if links & {url.rstrip("/") for url in RETIRED_URLS} or any("/event/05006488EE58E30A" in url for url in links):
        return CLEVELAND_ID
    if any("boletosexpress.com/oasis-ministry-s/88341" in url for url in links):
        return OASIS_ID
    if any("ticketsource.com/" in url and "/e-vgxqxl" in url for url in links):
        return MIAMI_ID
    return None


def unique(values: list) -> list:
    out = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def apply(root: Path = ROOT, today: str | None = None) -> None:
    today = today or dt.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    names = ("events.json", "supplemental-events.json", "config/manual-events.json")
    feeds = {name: json.loads((root / name).read_text()) for name in names}
    history_path = root / "event-history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else None
    entries = history.get("events", []) if history else []
    historical = [entry.get("event", entry) for entry in entries]
    all_rows = [row for rows in feeds.values() for row in rows] + historical

    for event_id, wanted in ((OASIS_ID, UPSERTS[OASIS_ID]), (MIAMI_ID, NEW_EVENTS[MIAMI_ID]), (CLEVELAND_ID, CLEVELAND)):
        previous = [row for row in all_rows if identity(row) == event_id]
        originals = [row for row in previous if str(row.get("id", "")).removeprefix("manual:") == event_id]
        canonical = copy.deepcopy(originals[0] if originals else {})
        # Superseded date/time boundaries must not survive the new start.
        for field in ("endDate", "endTime", "endDateTime", "mergedIntoId", "mergeReason"):
            canonical.pop(field, None)
        canonical.update(copy.deepcopy(wanted))
        canonical["firstSeen"] = min([wanted["firstSeen"]] + [row["firstSeen"] for row in previous if row.get("firstSeen")])
        canonical["sources"] = unique(wanted["sources"] + [source for row in originals for source in row.get("sources", [])])
        canonical["legacyEventPaths"] = unique(wanted["legacyEventPaths"] + [path for row in originals for path in row.get("legacyEventPaths", [])])
        canonical["id"] = event_id if event_id == CLEVELAND_ID else "manual:" + event_id
        for name, rows in feeds.items():
            rows[:] = [row for row in rows if identity(row) != event_id]
            if name == "events.json" and wanted["startDate"] >= today:
                rows.append(copy.deepcopy(canonical))
            elif name == "config/manual-events.json" and event_id != CLEVELAND_ID:
                rows.append(dict(copy.deepcopy(canonical), id=event_id))
        # Preserve archive provenance while preventing stale entries from
        # creating an old-date page or a second future/past Cleveland show.
        for entry in entries:
            row = entry.get("event", entry)
            if identity(row) != event_id:
                continue
            if str(row.get("id", "")).removeprefix("manual:") == event_id:
                row.update(copy.deepcopy(canonical))
                for field in ("endDate", "endTime", "endDateTime"):
                    row.pop(field, None)
            else:
                row.update(status="merged", mergedIntoId=canonical["id"], mergeReason="Consolidated with the canonical Beyond The Walls 3 listing; full lineup confirmed by promoter.")

    # Keep this event-specific artwork through the artist calendar refresh.
    # Hulvey's other shows continue to use their existing images.
    for row in [row for rows in feeds.values() for row in rows] + historical:
        if row.get("id") == DOVE_EVENT_ID:
            row.update(DOVE_ARTWORK)

    for name, rows in feeds.items():
        (root / name).write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    if history is not None:
        history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    apply()
    print("September 26 source corrections applied: concert starts, Oasis reschedule/artwork and Cleveland consolidation")
