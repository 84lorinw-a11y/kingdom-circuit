#!/usr/bin/env python3
"""Verified image and identity hotfixes for the Sep. 13 requested event batch."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = "2026-09-13"

PINS = {
    "one-day-fall-festival-aurora-2026": {
        "image": "assets/events/petrina-delacey-one-day-2026.jpg",
        "imageType": "artist",
        "imagePosition": "center",
        "imageOverride": True,
        "imageSource": "ONE DAY official festival site — Petrina DeLacey performance image",
        "imageSourceUrl": "https://onedaydenver.org/",
    },
    "kelo-worship-after-christmas-jacksonville-2026": {
        "image": "https://murrayhilltheatre.com/wp-content/uploads/2026/07/https-cdn.evbuc_.com-images-1188053564-306363782001-1-original.20260702-021736-1130x650.jpeg",
        "imageType": "event_artwork",
        "imagePosition": "center",
        "imageOverride": True,
        "imageSource": "Murray Hill Theatre official event page",
        "imageSourceUrl": "https://murrayhilltheatre.com/event/kelo-cho-presents-the-worship-after-christmas/",
    },
}

NEW_MAINSTREAM = {
    "cj-emulous-new-mainstream-miami-2026-11-05": {
        "title": "New Mainstream Tour — Miles Minnick, Tommy Zuko & CJ Emulous",
        "startDate": "2026-11-05",
        "startTime": "",
        "timezone": "America/New_York",
        "venue": "Venue not provided",
        "address": "",
        "city": "Miami",
        "state": "FL",
        "country": "US",
        "artists": ["Miles Minnick", "Tommy Zuko", "CJ Emulous"],
        "headliner": "Miles Minnick",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "",
        "officialUrl": "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-23",
        "image": "https://i.scdn.co/image/ab6761610000e5eb88d578e199bd2ce1021def5b",
        "imageType": "artist",
        "imagePosition": "center",
        "imageOverride": False,
        "lineupExplicit": True,
        "authority": "artist_calendar",
        "confidence": "high",
        "sourceName": "CJ Emulous official New Mainstream Tour calendar",
        "sources": [
            {
                "name": "CJ Emulous official New Mainstream Tour calendar",
                "url": "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-23",
                "type": "manual_verified",
                "authority": "artist_calendar",
                "priority": 100,
            },
            {
                "name": "Miles Minnick official tour page",
                "url": "https://milesminnick.com/tour",
                "type": "manual_verified",
                "authority": "artist_calendar",
                "priority": 94,
            },
        ],
        "notes": "Official artist calendar confirms the date and Miami, but no venue or direct ticket page. Time is left blank pending local venue/ticket confirmation.",
        "auditVerified": AUDIT,
    },
    "cj-emulous-new-mainstream-jacksonville-2026-11-08": {
        "title": "New Mainstream Tour — Miles Minnick, Tommy Zuko & CJ Emulous",
        "startDate": "2026-11-08",
        "startTime": "",
        "timezone": "America/New_York",
        "venue": "Venue not provided",
        "address": "",
        "city": "Jacksonville",
        "state": "FL",
        "country": "US",
        "artists": ["Miles Minnick", "Tommy Zuko", "CJ Emulous"],
        "headliner": "Miles Minnick",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "",
        "officialUrl": "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-26",
        "image": "https://i.scdn.co/image/ab6761610000e5eb88d578e199bd2ce1021def5b",
        "imageType": "artist",
        "imagePosition": "center",
        "imageOverride": False,
        "lineupExplicit": True,
        "authority": "artist_calendar",
        "confidence": "high",
        "sourceName": "CJ Emulous official New Mainstream Tour calendar",
        "sources": [
            {
                "name": "CJ Emulous official New Mainstream Tour calendar",
                "url": "https://www.cjemulous.com/event-details/new-mainstream-tour-w-miles-minnick-tommy-zuko-26",
                "type": "manual_verified",
                "authority": "artist_calendar",
                "priority": 100,
            },
            {
                "name": "Miles Minnick official tour page",
                "url": "https://milesminnick.com/tour",
                "type": "manual_verified",
                "authority": "artist_calendar",
                "priority": 94,
            },
        ],
        "notes": "Official artist calendar confirms the date and Jacksonville, but no venue or direct ticket page. Time is left blank pending local venue/ticket confirmation.",
        "auditVerified": AUDIT,
    },
}

USER_EVENTS = {
    "light-in-the-darkness-phoenix-2026": {
        "title": "Light in the Darkness",
        "startDate": "2026-10-31",
        "startTime": "16:00",
        "endTime": "21:30",
        "doorsTime": "15:00",
        "timezone": "America/Phoenix",
        "venue": "South Mountain Activity Complex",
        "address": "10401 S Central Ave",
        "city": "Phoenix",
        "state": "AZ",
        "country": "US",
        "artists": ["Jon Keith"],
        "headliner": "Jon Keith",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": "https://www.eventbrite.com/e/light-in-the-darkness-tickets-1997479295343",
        "officialUrl": "https://www.eventbrite.com/e/light-in-the-darkness-tickets-1997479295343",
        "image": "https://is1-ssl.mzstatic.com/image/thumb/Video211/v4/71/0c/9c/710c9c39-3dc7-0be5-a593-ab0ffc2fa618/Jobd846f8ea-4135-4580-8d0d-ed8f3cbb1f2a-190112036-PreviewImage_Preview_Image_Intermediate_nonvideo_372260380_2119658910-Time1744403657806.png/1200x675mv.webp",
        "imageType": "artist",
        "imagePosition": "center",
        "imageOverride": False,
        "price": "Free",
        "lineupExplicit": True,
        "advertisedBilling": ["Jon Keith", "Grace Graber", "trtle", "HLYVRS31", "CHVNCELLOR", "CHVRCHS62", "Adam Verdi"],
        "authority": "venue_ticket",
        "confidence": "high",
        "sourceName": "Official Eventbrite listing",
        "sources": [
            {
                "name": "Official Eventbrite listing",
                "url": "https://www.eventbrite.com/e/light-in-the-darkness-tickets-1997479295343",
                "type": "eventbrite",
                "authority": "venue_ticket",
                "priority": 112,
            },
            {
                "name": "City of Phoenix venue listing",
                "url": "https://www.phoenix.gov/calendar/parks-events/south-mountain-grand-opening-.html",
                "type": "manual_verified",
                "authority": "venue",
                "priority": 86,
            },
            {
                "name": "Bandsintown event listing",
                "url": "https://www.bandsintown.com/e/108849019-trtle-at-south-mountain-activity-complex",
                "type": "manual_verified",
                "authority": "artist_calendar",
                "priority": 76,
            },
        ],
        "ageRestriction": "Under 18 with parent or legal guardian",
        "notes": "Free public event. Official ticket page lists doors at 3:00 PM and event hours 4:00–9:30 PM. User-provided organizer flyer confirms Jon Keith as the featured headliner.",
        "auditVerified": "2026-09-14",
    },
}


def _source_urls(row: dict) -> set[str]:
    values = {str(row.get("officialUrl") or "")}
    values.update(
        str(item.get("url") or "")
        for item in row.get("sources") or []
        if isinstance(item, dict)
    )
    return {value for value in values if value}


def _repair_new_mainstream(rows: list[dict], manual: bool) -> None:
    target_ids = set(NEW_MAINSTREAM)
    target_urls = {event["officialUrl"] for event in NEW_MAINSTREAM.values()}

    def is_target(row: dict) -> bool:
        key = str(row.get("id") or "").removeprefix("manual:")
        if key in target_ids:
            return True
        if _source_urls(row) & target_urls:
            return True
        return (
            str(row.get("title") or "").startswith("New Mainstream Tour")
            and row.get("startDate") in {"2026-11-05", "2026-11-08"}
            and str(row.get("state") or "").upper() == "FL"
        )

    rows[:] = [row for row in rows if not is_target(row)]
    for event_id, event in NEW_MAINSTREAM.items():
        value = dict(event)
        value["id"] = event_id if manual else f"manual:{event_id}"
        rows.append(value)

    repaired = [
        row for row in rows
        if str(row.get("id") or "").removeprefix("manual:") in target_ids
    ]
    if len(repaired) != 2:
        raise SystemExit(f"Expected two distinct New Mainstream Florida records; found {len(repaired)}")
    slots = {(row.get("startDate"), row.get("city")) for row in repaired}
    if slots != {("2026-11-05", "Miami"), ("2026-11-08", "Jacksonville")}:
        raise SystemExit(f"New Mainstream Florida records merged or mislocated: {sorted(slots)}")
    if len({row.get("officialUrl") for row in repaired}) != 2:
        raise SystemExit("New Mainstream Florida records lost their distinct official event URLs")
    if any(row.get("ticketUrl") for row in repaired):
        raise SystemExit("New Mainstream Florida records must not expose a generic tour page as a direct ticket URL")


def _repair_user_events(rows: list[dict], manual: bool) -> None:
    for event_id, event in USER_EVENTS.items():
        official = str(event.get("officialUrl") or "")
        date = event.get("startDate")
        city = str(event.get("city") or "").casefold()
        title = str(event.get("title") or "").casefold()

        def is_target(row: dict) -> bool:
            key = str(row.get("id") or "").removeprefix("manual:")
            if key == event_id:
                return True
            if official and official in _source_urls(row):
                return True
            return (
                row.get("startDate") == date
                and str(row.get("city") or "").casefold() == city
                and str(row.get("title") or "").casefold() == title
            )

        rows[:] = [row for row in rows if not is_target(row)]
        value = dict(event)
        value["id"] = event_id if manual else f"manual:{event_id}"
        rows.append(value)


def apply_requested_image_hotfix() -> None:
    # Sep. 13 requested additions are durable only in config/manual-events.json.
    # events.json is the generated/runtime copy. supplemental-events.json must not
    # be repopulated here or the same event exists in two durable inputs.
    for rel in ("config/manual-events.json", "events.json"):
        path = ROOT / rel
        rows = json.loads(path.read_text(encoding="utf-8"))
        manual = rel == "config/manual-events.json"
        _repair_new_mainstream(rows, manual)
        _repair_user_events(rows, manual)

        changed = 0
        for row in rows:
            key = str(row.get("id") or "").removeprefix("manual:")
            pin = PINS.get(key)
            if not pin:
                continue
            row.update(pin)
            changed += 1
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if changed != len(PINS):
            raise SystemExit(f"{rel}: expected {len(PINS)} requested image pins, found {changed}")


if __name__ == "__main__":
    apply_requested_image_hotfix()
