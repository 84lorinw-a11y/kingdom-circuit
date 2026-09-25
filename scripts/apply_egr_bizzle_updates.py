#!/usr/bin/env python3
"""Keep the reviewed EGR portrait and official Whittier/Chandler listings on refresh."""
from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PORTRAIT = "assets/artists/egr-spotify-primary.jpg"
PORTRAIT_SOURCE = "https://open.spotify.com/artist/4EJIkbig1thbV3C3B68c56"
OLD_PORTRAIT = "assets/artists/egr.webp"
VERIFIED_AT = "2026-09-25T18:17:56Z"
EVENTS = (
    {
        "id": "egr-2026-09-26-whittier-ca",
        "title": "Trickle Effect — EGR & Kim Hitt-Galvan",
        "startDate": "2026-09-26", "endDate": "2026-09-26",
        "startTime": "18:30", "endTime": "20:30", "doorsTime": "17:30",
        "startDateTime": "2026-09-26T18:30:00-07:00", "endDateTime": "2026-09-26T20:30:00-07:00",
        "timezone": "America/Los_Angeles",
        "venue": "Revolution Friends Church", "address": "15911 E Whittier Blvd",
        "city": "Whittier", "state": "CA", "postalCode": "90603", "country": "US",
        "artists": ["EGR"], "headliner": "EGR",
        "advertisedBilling": ["EGR", "Kim Hitt-Galvan"],
        "officialBill": ["EGR", "Kim Hitt-Galvan"],
        "officialUrl": "https://www.eventbrite.com/e/trickle-effect-tickets-1997988233591",
        "ticketUrl": "https://www.eventbrite.com/e/trickle-effect-tickets-1997988233591",
        "image": "assets/events/trickle-effect-whittier-2026-09-26.jpg",
        "imageSource": "Official Trickle Effect Eventbrite flyer",
        "imageSourceUrl": "https://cdn.evbuc.com/images/1191103818/2100773501163/1/original.20260814-195318",
        "detailImageLayout": "landscape",
        "legacyEventPaths": ["/event/egr-live-whittier-2026-09-26-whittier-137bc9/"],
        "legacyEventNotice": "This listing now includes the official Trickle Effect name, venue, time and lineup.",
    },
    {
        "id": "egr-2026-10-03-chandler-az",
        "title": "Zion Ultra Lounge — Christian Music Pop-Up Concert",
        "startDate": "2026-10-03", "endDate": "2026-10-04",
        "startTime": "19:00", "endTime": "00:00", "doorsTime": "18:30",
        "startDateTime": "2026-10-03T19:00:00-07:00", "endDateTime": "2026-10-04T00:00:00-07:00",
        "timezone": "America/Phoenix",
        "venue": "Vybe Event Center", "address": "2301 S Stearman Dr",
        "city": "Chandler", "state": "AZ", "postalCode": "85286", "country": "US",
        "artists": ["EGR", "Bizzle"], "headliner": "",
        "advertisedBilling": ["Zacardi Cortez", "Dre’Lo", "EGR", "Bizzle", "TH3RDDAE Da Mouthpiece"],
        "officialBill": ["Zacardi Cortez", "Dre’Lo", "EGR", "Bizzle", "TH3RDDAE Da Mouthpiece"],
        "officialUrl": "https://www.eventbrite.com/e/zion-ultra-lounge-presents-tickets-2001784484279",
        "ticketUrl": "https://www.eventbrite.com/e/zion-ultra-lounge-presents-tickets-2001784484279",
        "image": "assets/events/zion-ultra-lounge-chandler-2026-10-03.jpg",
        "imageSource": "Official Zion Ultra Lounge Eventbrite flyer",
        "imageSourceUrl": "https://cdn.evbuc.com/images/1193966554/3014861055103/1/original.20260920-205737",
        "legacyEventPaths": [
            "/event/egr-live-chandler-2026-10-03-chandler-3f4bba/",
            "/event/bizzle-at-vybe-event-center-2026-10-03-chandler-998ccf/",
        ],
        "legacyEventNotice": "The EGR and Bizzle listings have been combined into this confirmed Zion Ultra Lounge concert.",
        "mergedFromIds": ["bandsintown:108954639"],
    },
)
for event in EVENTS:
    event.update({
        "eventType": "concert", "status": "scheduled", "lineupExplicit": True,
        "imageType": "event_artwork", "imageOverride": True, "imagePosition": "center",
        "sourceName": "Official Eventbrite listing", "authority": "official_event", "confidence": "high",
        "firstSeen": "2026-08-09T00:00:00Z", "lastVerified": VERIFIED_AT,
        "sources": [{"name": "Official Eventbrite listing", "url": event["officialUrl"],
                     "type": "official_event", "authority": "official_event", "priority": 112}],
    })


def matches(row: dict, event: dict) -> bool:
    # Match confirmed identities, never every appearance by an artist on a date.
    event_id = str(row.get("id", ""))
    if event_id.removeprefix("manual:") == event["id"] or event_id in event.get("mergedFromIds", []):
        return True
    source_id = event["officialUrl"].rsplit("-", 1)[-1]
    return any("eventbrite.com/" in str(row.get(field, "")) and source_id in str(row.get(field, ""))
               for field in ("officialUrl", "ticketUrl"))


def unique(values: list) -> list:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def portrait_fallback(row: dict) -> None:
    if row.get("image") == OLD_PORTRAIT:
        row.update(image=PORTRAIT, imageType="artist", imagePosition="50% 0%",
                   imageSource="EGR official Spotify portrait", imageSourceUrl=PORTRAIT_SOURCE)


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def apply(root: Path = ROOT, today: str | None = None) -> None:
    today = today or dt.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    files = ("config/manual-events.json", "events.json", "supplemental-events.json")
    feeds = {name: json.loads((root / name).read_text(encoding="utf-8")) for name in files}
    history_path = root / "event-history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else None
    historical = history.get("events", []) if history else []
    all_rows = [row for rows in feeds.values() for row in rows] + historical

    for event in EVENTS:
        previous = [r for r in all_rows if matches(r, event)]
        # Prefer the canonical record's additional metadata over a duplicate's.
        canonical = {}
        for row in reversed(previous):
            if str(row.get("id", "")).removeprefix("manual:") == event["id"]:
                canonical.update(copy.deepcopy(row))
        canonical.update(copy.deepcopy(event))
        canonical["firstSeen"] = min([event["firstSeen"]] + [r["firstSeen"] for r in previous if r.get("firstSeen")])
        canonical["sources"] = unique(event["sources"] + [s for r in previous for s in r.get("sources", [])])
        for key in ("legacyEventPaths", "mergedFromIds"):
            values = unique(event.get(key, []) + [v for r in previous for v in r.get(key, [])])
            if values:
                canonical[key] = values
        for key in ("mergedIntoId", "mergedInto", "mergeReason"):
            canonical.pop(key, None)
        for name, rows in feeds.items():
            rows[:] = [r for r in rows if not matches(r, event)]
            if name == "config/manual-events.json" or (name == "events.json" and event["endDate"] >= today):
                record = copy.deepcopy(canonical)
                record["id"] = event["id"] if name.startswith("config/") else "manual:" + event["id"]
                rows.append(record)
        # Correct existing archived records without manufacturing an early archive.
        if any(matches(r, event) for r in historical):
            historical[:] = [r for r in historical if not matches(r, event)]
            historical.append(dict(copy.deepcopy(canonical), id="manual:" + event["id"]))

    for name, rows in feeds.items():
        for row in rows:
            portrait_fallback(row)
        rows.sort(key=lambda r: (r.get("startDate", ""), r.get("startTime", ""), r.get("title", "")))
        write(root / name, rows)
    if history is not None:
        for row in historical:
            portrait_fallback(row)
        write(history_path, history)

    artists_path = root / "config/artists.json"
    artists = json.loads(artists_path.read_text(encoding="utf-8"))
    for artist in artists:
        if artist.get("name") == "EGR":
            artist.update(imageUrl=PORTRAIT, imagePosition="50% 0%", officialImageSource=PORTRAIT_SOURCE)
    write(artists_path, artists)


if __name__ == "__main__":
    apply()
    print("EGR portrait and official Trickle Effect / Zion listings preserved; duplicate Bizzle listing reconciled")
