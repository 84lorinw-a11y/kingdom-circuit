#!/usr/bin/env python3
"""Keep the verified ECHO Nights 26 listing and official TicketSpice artwork durable."""

import argparse
import json
from pathlib import Path

EVENT_ID = "manual:ticketspice:echo-nights-26-brookfield-2026"
IMAGE = "assets/events/echo-nights-26.jpg"
TICKET_URL = "https://atkministry.ticketspice.com/echo-nights-26"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default=".", help="Repository/site root to repair")
    args = parser.parse_args()
    root = Path(args.site)
    supplemental_path = root / "supplemental-events.json"
    image_path = root / IMAGE

    if not image_path.is_file() or image_path.stat().st_size < 100_000:
        raise SystemExit(f"Verified ECHO Nights artwork missing or unexpectedly small: {image_path}")

    events = json.loads(supplemental_path.read_text(encoding="utf-8"))
    matches = [event for event in events if event.get("id") == EVENT_ID]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one ECHO Nights 26 event; found {len(matches)}")

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
        "artists": ["Kijan Boone", "Austin Joyce", "VVS Big Rock", "Kaymilinn"],
        "headliner": "Kijan Boone",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": TICKET_URL,
        "officialUrl": TICKET_URL,
        "image": IMAGE,
        "imageType": "event_artwork",
        "imagePosition": "center",
        "imageOverride": True,
        "imageSource": "Official ATK Ministry / TicketSpice event artwork supplied by organizer page",
        "sourceName": "Official TicketSpice listing",
        "authority": "venue_ticket",
        "confidence": "high",
        "lineupExplicit": True,
        "notes": "Doors 6 PM; show 7 PM; all ages welcome. Official ATK Ministry event artwork locked for this listing.",
    })

    supplemental_path.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"ECHO Nights 26 repaired with official artwork: {IMAGE}")


if __name__ == "__main__":
    main()
