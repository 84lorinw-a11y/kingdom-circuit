#!/usr/bin/env python3
"""Keep the verified ECHO Nights 26 listing and supplied official ATK artwork durable."""

import argparse
import hashlib
import json
from pathlib import Path

EVENT_ID = "manual:ticketspice:echo-nights-26-brookfield-2026"
IMAGE = "assets/events/echo-nights-26.jpg"
IMAGE_SHA256 = "39932408e919ac878f1be5c35205f563302aec26648a9570398d80b3ae66e2ab"
TICKET_URL = "https://atkministry.ticketspice.com/echo-nights-26"
SOURCE_FILES = ("events.json", "supplemental-events.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=".", help="Repository/site root to repair")
    args = parser.parse_args()
    root = Path(args.site)
    image_path = root / IMAGE

    if not image_path.is_file():
        raise SystemExit(f"Verified ECHO Nights artwork is missing: {image_path}")
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
    if digest != IMAGE_SHA256:
        raise SystemExit(
            f"Verified ECHO Nights artwork hash mismatch: {image_path} "
            f"expected {IMAGE_SHA256}, got {digest}"
        )

    repaired = 0
    found = 0
    for filename in SOURCE_FILES:
        path = root / filename
        if not path.is_file():
            continue
        events = json.loads(path.read_text(encoding="utf-8"))
        matches = [event for event in events if event.get("id") == EVENT_ID]
        if len(matches) > 1:
            raise SystemExit(f"{filename}: duplicate ECHO Nights 26 events found: {len(matches)}")
        if not matches:
            continue

        found += 1
        event = matches[0]
        event.update({
            "title": "ECHO Nights 26",
            "startDate": "2026-10-02",
            "startTime": "19:00",
            "timezone": "America/Chicago",
            "venue": "Elmbrook Church",
            "address": "777 S Barker Rd",
            "city": "Brookfield",
            "state": "WI",
            "country": "US",
            "artists": ["Kijan Boone", "Austin Joyce", "VVS Big Rock", "Kaymilinn", "DJ Bryce G"],
            "headliner": "Kijan Boone",
            "eventType": "concert",
            "status": "scheduled",
            "ticketUrl": TICKET_URL,
            "officialUrl": TICKET_URL,
            "image": IMAGE,
            "imageType": "event_artwork",
            "imagePosition": "center top",
            "imageOverride": True,
            "imageSource": "Official ATK Ministry ECHO Nights 26 collage artwork",
            "imageSourceUrl": TICKET_URL,
            "sourceName": "Official TicketSpice listing",
            "authority": "venue_ticket",
            "confidence": "high",
            "lineupExplicit": True,
            "notes": "Doors 6 PM; show 7 PM; all ages welcome. Official ATK Ministry collage artwork locked for this listing.",
        })
        path.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        repaired += 1
        print(f"ECHO Nights 26 repaired in {filename} with official artwork: {IMAGE}")

    if found == 0:
        raise SystemExit("ECHO Nights 26 event was not found in any source file")
    print(f"ECHO Nights 26 official guard passed across {found} source file(s).")


if __name__ == "__main__":
    main()
