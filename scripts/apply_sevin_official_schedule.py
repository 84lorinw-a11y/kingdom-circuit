#!/usr/bin/env python3
"""Keep Sevin's published schedule aligned to the official HOG MOB calendar."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
HOGMOB_URL = "https://hogmob.com/sevin-live-concert/"


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
        "officialUrl": HOGMOB_URL,
        "image": "assets/artists/sevin.webp",
        "price": "Donate what you can; VIP $110",
        "sourceName": "HOG MOB official Sevin tour",
        "authority": "artist_calendar",
        "confidence": "high",
        "lineupExplicit": True,
        "sources": [{
            "name": "HOG MOB official Sevin tour",
            "url": HOGMOB_URL,
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


SEVIN_EVENTS = [
    # Historical Aug 29 ticket destination is retained with the archived record.
    sevin_event("sevin-live-san-diego-2026-08-29", "2026-08-29", "San Diego", "CA", "https://www.eventbrite.com/e/1976534238113?aff=oddtdtcreator"),
    # These four Eventbrite destinations were confirmed broken during the Sep 12 audit.
    sevin_event("sevin-live-kansas-city-2026-09-26", "2026-09-26", "Kansas City", "MO"),
    sevin_event("sevin-live-nashville-2026-10-24", "2026-10-24", "Nashville", "TN"),
    sevin_event("sevin-live-charlotte-2026-11-21", "2026-11-21", "Charlotte", "NC"),
    sevin_event("sevin-live-sacramento-2026-12-05", "2026-12-05", "Sacramento", "CA"),
]

CANONICAL_IDS = {event["id"] for event in SEVIN_EVENTS}
CANONICAL_DATES = {event["startDate"] for event in SEVIN_EVENTS}


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


def main() -> int:
    events = load(EVENTS_FILE)
    supplemental = load(SUPPLEMENTAL_FILE)

    before_events = len(events)
    events = [
        event for event in events
        if not (is_sevin(event) and str(event.get("startDate") or "") in CANONICAL_DATES)
    ]
    removed = before_events - len(events)

    supplemental = [
        event for event in supplemental
        if str(event.get("id") or "") not in CANONICAL_IDS
        and not (is_sevin(event) and str(event.get("startDate") or "") in CANONICAL_DATES)
    ]
    supplemental.extend(SEVIN_EVENTS)
    supplemental.sort(key=lambda event: (str(event.get("startDate") or "9999-12-31"), str(event.get("title") or "")))

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
            if is_sevin(event) and event.get("startDate") == expected["startDate"]
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
