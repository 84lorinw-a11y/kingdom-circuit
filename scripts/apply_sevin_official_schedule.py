#!/usr/bin/env python3
"""Keep Sevin's published schedule aligned to the official HOG MOB calendar."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
HOGMOB_URL = "https://hogmob.com/mob-tour/"
HISTORICAL_HOGMOB_URL = "https://hogmob.com/sevin-live-concert/"


def sevin_event(event_id: str, start_date: str, city: str, state: str, ticket_url: str = "") -> dict[str, Any]:
    event: dict[str, Any] = {
        "id": event_id,
        "title": "Sevin Live Concert",
        "startDate": start_date,
        "startTime": "20:00",
        "venue": "Location TBD",
        "address": "",
        "city": city,
        "state": state,
        "country": "US",
        "artists": ["Sevin"],
        "headliner": "Sevin",
        "eventType": "concert",
        "status": "scheduled",
        "ticketUrl": ticket_url,
        "officialUrl": HISTORICAL_HOGMOB_URL,
        "image": "assets/artists/sevin.webp",
        "price": "Donate what you can; VIP $110",
        "sourceName": "HOG MOB official Sevin tour",
        "authority": "artist_calendar",
        "confidence": "high",
        "lineupExplicit": True,
        "sources": [{
            "name": "HOG MOB official Sevin tour",
            "url": HISTORICAL_HOGMOB_URL,
            "type": "manual_verified",
            "authority": "artist_calendar",
            "priority": 100,
        }],
    }
    if ticket_url:
        event["sources"].append({
            "name": "Official ticket link from HOG MOB",
            "url": ticket_url,
            "type": "venue_ticket",
            "authority": "venue_ticket",
            "priority": 94,
        })
    else:
        event["ticketAvailability"] = "needs_confirmation"
        event["notes"] = "HOG MOB confirms the show date; current ticket availability needs confirmation."
    return event


def confirmed_event(event_id: str, start_date: str, city: str, state: str,
                    venue: str, address: str, postal_code: str,
                    timezone: str, detail_url: str, flyer_url: str,
                    first_seen: str) -> dict[str, Any]:
    event = sevin_event(event_id, start_date, city, state)
    event.update({
        "startTime": "19:00",
        "timezone": timezone,
        "venue": venue,
        "address": address,
        "postalCode": postal_code,
        "officialUrl": detail_url,
        "advertisedBilling": ["Sevin", "HOG MOB Dontae"],
        "officialBill": ["Sevin", "HOG MOB Dontae"],
        "supportActs": ["HOG MOB Dontae"],
        "price": "Free concert; see official details for VIP options",
        "firstSeen": first_seen,
        "auditVerified": "2026-09-25",
        "notes": "Official city concert flyer confirms a 7 PM concert and a separate 6 PM VIP meet-and-greet.",
        "sources": [
            {"name": "HOG MOB official city schedule", "url": detail_url,
             "type": "manual_verified", "authority": "artist_calendar", "priority": 100},
            {"name": "HOG MOB official concert flyer", "url": flyer_url,
             "type": "manual_verified", "authority": "artist_calendar", "priority": 100},
        ],
    })
    return event


SEVIN_EVENTS = [
    # Historical Aug 29 ticket destination is retained with the archived record.
    sevin_event("sevin-live-san-diego-2026-08-29", "2026-08-29", "San Diego", "CA", "https://www.eventbrite.com/e/1976534238113?aff=oddtdtcreator"),
    confirmed_event(
        "sevin-live-millville-2026-09-26", "2026-09-26", "Millville", "NJ",
        "Dwelling Place Church", "125 N 2nd St", "08332", "America/New_York",
        "https://hogmob.com/millville/",
        "https://hogmob.com/wp-content/uploads/2026/08/Sevin-live-NJ.jpg",
        # Owner classifies this as a correction to the existing September 26
        # listing. Retain its discovery age (archive official:5519f66ef9eac3632648).
        "2026-08-09T00:00:00Z",
    ),
    confirmed_event(
        "sevin-live-nashville-2026-10-24", "2026-10-24", "Old Hickory", "TN",
        "We Are Church Nashville", "1501 Hadley Ave", "37138", "America/Chicago",
        "https://hogmob.com/nashville/",
        "https://hogmob.com/wp-content/uploads/2026/08/Sevin-live-TN.jpg",
        "2026-08-09T00:00:00Z",
    ),
]
SEVIN_EVENTS[1].update({
    "image": "assets/events/sevin-live-millville-2026-09-26.png",
    "imageType": "event_artwork",
    "imageOverride": True,
    "imagePosition": "center",
    "imageSource": "Owner-supplied official HOG MOB Millville concert flyer",
    "imageSourceUrl": "https://hogmob.com/wp-content/uploads/2026/08/Sevin-live-NJ.jpg",
})
SEVIN_EVENTS[-1]["legacyEventPaths"] = [
    "/event/sevin-live-concert-2026-10-24-nashville-76d537/",
]
SEVIN_EVENTS[-1]["legacyEventNotice"] = "The venue location has been updated to Old Hickory in the Nashville area. The concert date is unchanged."

# Unsupported listings are unpublished, not labeled canceled or redirected to
# unrelated concerts. Sacramento Nov 20–22 is a tour weekend, not a confirmed
# concert night. Oahu Jan 14–16 has conflicting 2026/2027 source years. Keep both
# off the calendar until individual performance details are confirmed.
RETIRED_STOPS = {
    ("2026-09-26", "kansas city", "MO"),
    ("2026-11-21", "charlotte", "NC"),
    ("2026-12-05", "sacramento", "CA"),
}
RETIRED_IDS = {
    "sevin-live-kansas-city-2026-09-26",
    "sevin-live-charlotte-2026-11-21",
    "sevin-live-sacramento-2026-12-05",
}

CANONICAL_IDS = {event["id"] for event in SEVIN_EVENTS}
CANONICAL_STOPS = {
    (event["startDate"], event["city"].casefold(), event["state"])
    for event in SEVIN_EVENTS
} | {("2026-10-24", "nashville", "TN")}


def load(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        value = []
    if not isinstance(value, list):
        raise SystemExit(f"Expected JSON array: {path}")
    return [item for item in value if isinstance(item, dict)]


def save(path: Path, value: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_sevin(event: dict[str, Any]) -> bool:
    return "sevin" in {str(name or "").strip().casefold() for name in event.get("artists", [])}


def managed_event(event: dict[str, Any]) -> bool:
    if str(event.get("id") or "") in CANONICAL_IDS | RETIRED_IDS:
        return True
    city = str(event.get("city") or "").strip().casefold().removeprefix("sponsor ")
    stop = (str(event.get("startDate") or ""), city, str(event.get("state") or "").upper())
    return is_sevin(event) and stop in CANONICAL_STOPS | RETIRED_STOPS


def normalize_schedule(events: list[dict], supplemental: list[dict]) -> tuple[list[dict], list[dict]]:
    """Replace only audited stops, preserving unrelated Sevin performances."""
    events = [event for event in events if not managed_event(event)]
    supplemental = [event for event in supplemental if not managed_event(event)]
    supplemental.extend(deepcopy(SEVIN_EVENTS))
    supplemental.sort(key=lambda event: (str(event.get("startDate") or "9999-12-31"), str(event.get("title") or "")))
    return events, supplemental


def main() -> int:
    events = load(EVENTS_FILE)
    supplemental = load(SUPPLEMENTAL_FILE)

    before_events = len(events)
    events, supplemental = normalize_schedule(events, supplemental)
    removed = before_events - len(events)

    save(EVENTS_FILE, events)
    save(SUPPLEMENTAL_FILE, supplemental)

    all_published = [*events, *supplemental]
    malformed = [
        event for event in all_published
        if is_sevin(event) and str(event.get("city") or "").casefold().startswith("sponsor ")
    ]
    if malformed:
        raise SystemExit(f"Malformed Sevin city labels remain: {malformed}")

    for expected in SEVIN_EVENTS:
        matches = [
            event for event in all_published
            if event.get("id") == expected["id"]
        ]
        if len(matches) != 1 or matches[0].get("city") != expected["city"]:
            raise SystemExit(f"Sevin canonicalization failed for {expected['startDate']}: {matches}")
        if expected["startDate"] > "2026-09-12" and matches[0].get("ticketUrl"):
            raise SystemExit(f"Broken future Sevin ticket link returned for {expected['startDate']}")

    # Preserve other verified editorial corrections after collector/curation output.
    from apply_verified_content_overrides import main as apply_verified_content_overrides
    from apply_deonte_hall_submission import main as apply_deonte_hall_submission
    from apply_sep12_phase2_repairs import main as apply_sep12_phase2_repairs

    apply_verified_content_overrides()
    apply_deonte_hall_submission()
    apply_sep12_phase2_repairs()

    print(
        f"Sevin schedule normalized from HOG MOB: removed {removed} malformed/duplicate collected record(s); "
        f"ensured {len(SEVIN_EVENTS)} official dates without unsupported future ticket offers."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
