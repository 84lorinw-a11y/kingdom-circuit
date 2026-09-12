#!/usr/bin/env python3
"""Durable, source-backed repairs confirmed by the September 12, 2026 audit."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVENT_FILES = (
    ROOT / "events.json",
    ROOT / "supplemental-events.json",
    ROOT / "config" / "manual-events.json",
)
RARE_EVENTBRITE_ID = "1986268845586"
RARE_CANCEL_URL = "https://www.eventbrite.com/e/cancelled-rare-of-breed-tickets-1986268845586"
FAITH_JAM_ID = "official:95cc80c13713dfecaf6d"
FAITH_JAM_URL = "https://www.eventbrite.com/e/faith-jam-2026-tickets-1985341605185"
MIKE_TEEZY_ID = "official:4e2fc5c7c02ab1d34b9e"
MIKE_TEEZY_URL = "https://music.apple.com/us/concerts/ce.01a1c61a-49a9-4e19-b629-46bac43b4970"
FASTIVALLE_ID = "official:ea0342f4771e9f9f1dfc"
FASTIVALLE_URL = "https://music.apple.com/us/concerts/ce.7570f0f7-b826-4400-a6f0-034778e98568"
KINGDOM_CHOICE_ID = "official:64bbcd477c3a36104df3"
KINGDOM_CHOICE_URL = "https://www.queenstheatre.org/events/kingdom-choice-awards-2026-dqr9"
ZAUNTEE_MERGES = {
    "supplemental:skema-boy-2026-11-01-new-york-ny": ("ticketmaster:k7vGF_CBswXt6", "17:00", "18:30", "https://mercuryeastpresents.com/tm-event/zauntee-god-remembers-tour/"),
    "supplemental:skema-boy-2026-11-08-atlanta-ga": ("ticketmaster:vvG1zZ_ClQMRrF", "19:00", "20:00", "https://www.masqueradeatlanta.com/events/zauntee/"),
    "supplemental:skema-boy-2026-11-19-los-angeles-ca": ("ticketmaster:vvG10Z_CMA3B0H", "21:30", "22:00", "https://themoroccan.com/tm-event/zauntee-god-remembers-tour/"),
}


def load(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise SystemExit(f"Expected an event array in {path}")
    return value


def save(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_source(event: dict, source: dict) -> None:
    sources = event.setdefault("sources", [])
    if not any(isinstance(item, dict) and item.get("url") == source["url"] for item in sources):
        sources.append(source)


def apply() -> dict[str, int]:
    report = {"cancelledRecords": 0, "faithJamRecords": 0, "mikeTeezyRecords": 0, "fastivalleRecords": 0, "kingdomChoiceRecords": 0, "zaunteeCanonicalRecords": 0, "zaunteeRetiredRecords": 0}
    cancellation_source = {
        "name": "Official Eventbrite cancellation notice",
        "url": RARE_CANCEL_URL,
        "type": "eventbrite",
        "authority": "venue_ticket",
        "priority": 120,
    }
    faith_source = {
        "name": "Official Faith Jam Eventbrite poster",
        "url": FAITH_JAM_URL,
        "type": "eventbrite",
        "authority": "official_event",
        "priority": 112,
    }

    for path in EVENT_FILES:
        rows = load(path)
        by_id = {event.get("id"): event for event in rows}
        changed = False
        for event in rows:
            urls = " ".join(str(event.get(key) or "") for key in ("officialUrl", "ticketUrl"))
            if RARE_EVENTBRITE_ID in urls:
                event["status"] = "cancelled"
                event["cancellationConfirmed"] = True
                event["cancellationConfirmedAt"] = "2026-09-12"
                event["officialUrl"] = RARE_CANCEL_URL
                event["ticketUrl"] = RARE_CANCEL_URL
                event["sourceName"] = "Official Eventbrite cancellation notice"
                event["notes"] = "Cancelled by the organizer. This page is retained as a cancellation notice."
                append_source(event, cancellation_source)
                report["cancelledRecords"] += 1
                changed = True

            if event.get("id") == FAITH_JAM_ID:
                artists = event.setdefault("artists", [])
                if "Brother Bo" not in artists:
                    artists.append("Brother Bo")
                event["venue"] = "White County Fairgrounds"
                event["address"] = "565 Hale Street"
                append_source(event, faith_source)
                event["auditVerified"] = "2026-09-12"
                report["faithJamRecords"] += 1
                changed = True

            if event.get("id") == MIKE_TEEZY_ID:
                event["startTime"] = "18:00"
                event["timezone"] = "America/New_York"
                event.pop("endDate", None)
                event["officialUrl"] = MIKE_TEEZY_URL
                event["sourceName"] = "Exact Apple Music event page"
                append_source(event, {"name": "Exact Apple Music event page", "url": MIKE_TEEZY_URL, "type": "artist_calendar", "authority": "artist_calendar", "priority": 112})
                event["notes"] = "Apple Music displays 6:00 PM on November 7. The former 11:00 PM value and November 8 end date resulted from preserving UTC as local time."
                event["auditVerified"] = "2026-09-12"
                report["mikeTeezyRecords"] += 1
                changed = True

            if event.get("id") == FASTIVALLE_ID:
                event["venue"] = "Camptown, Inc."
                event["address"] = "1010 W 64th St"
                event["startTime"] = "19:00"
                event["timezone"] = "America/Indiana/Indianapolis"
                event["officialUrl"] = FASTIVALLE_URL
                event["sourceName"] = "Exact Apple Music event page"
                append_source(event, {"name": "Exact Apple Music event page", "url": FASTIVALLE_URL, "type": "artist_calendar", "authority": "artist_calendar", "priority": 112})
                event["notes"] = "Official listing publishes 7:00 PM but does not identify it as doors or performance time."
                event["auditVerified"] = "2026-09-12"
                report["fastivalleRecords"] += 1
                changed = True

            if event.get("id") == KINGDOM_CHOICE_ID:
                event["title"] = "Kingdom Choice Awards 2026"
                event["startTime"] = "19:00"
                event["timezone"] = "America/New_York"
                event["venue"] = "The Claire Shulman Theater at Queens Theatre"
                event["address"] = "14 United Nations Avenue South"
                event["city"] = "Corona"
                event["ticketUrl"] = KINGDOM_CHOICE_URL
                event["officialUrl"] = KINGDOM_CHOICE_URL
                event["sourceName"] = "Queens Theatre event and tickets"
                append_source(event, {"name": "Queens Theatre event and tickets", "url": KINGDOM_CHOICE_URL, "type": "venue_ticket", "authority": "official_venue", "priority": 120})
                event["auditVerified"] = "2026-09-12"
                report["kingdomChoiceRecords"] += 1
                changed = True

        for retired_id, (canonical_id, doors, performance, venue_url) in ZAUNTEE_MERGES.items():
            canonical = by_id.get(canonical_id)
            retired = by_id.get(retired_id)
            if canonical:
                canonical["artists"] = list(dict.fromkeys([*canonical.get("artists", []), "Skema Boy"]))
                canonical["doorsTime"] = doors
                canonical["performanceTime"] = performance
                canonical["startTime"] = performance
                canonical["officialUrl"] = venue_url
                canonical["sourceName"] = "Official venue event page"
                canonical["mergedIds"] = list(dict.fromkeys([*canonical.get("mergedIds", []), retired_id]))
                append_source(canonical, {"name": "Official venue event page", "url": venue_url, "type": "venue", "authority": "official_venue", "priority": 120})
                if retired:
                    for source in retired.get("sources", []):
                        if isinstance(source, dict) and source.get("url"):
                            append_source(canonical, source)
                report["zaunteeCanonicalRecords"] += 1
                changed = True
            if retired:
                retired["status"] = "merged"
                retired["mergedIntoId"] = canonical_id
                retired["notes"] = "Duplicate support-artist listing consolidated into the canonical official-venue event."
                report["zaunteeRetiredRecords"] += 1
                changed = True

        if changed:
            save(path, rows)
    return report


def check() -> None:
    for path in EVENT_FILES:
        rows = load(path)
        rare = [event for event in rows if RARE_EVENTBRITE_ID in json.dumps(event)]
        if len(rare) != 1 or rare[0].get("status") != "cancelled" or not rare[0].get("cancellationConfirmed"):
            raise SystemExit(f"Rare of Breed cancellation is not durable in {path}")
        faith = [event for event in rows if event.get("id") == FAITH_JAM_ID]
        if faith:
            event = faith[0]
            if "Brother Bo" not in event.get("artists", []):
                raise SystemExit(f"Brother Bo is missing from Faith Jam in {path}")
            if event.get("venue") != "White County Fairgrounds" or event.get("address") != "565 Hale Street":
                raise SystemExit(f"Faith Jam venue fields are incorrect in {path}")
        mike = [event for event in rows if event.get("id") == MIKE_TEEZY_ID]
        if mike and (mike[0].get("startTime") != "18:00" or mike[0].get("endDate")):
            raise SystemExit(f"Mike Teezy time correction is not durable in {path}")
        fastivalle = [event for event in rows if event.get("id") == FASTIVALLE_ID]
        if fastivalle and (fastivalle[0].get("venue") != "Camptown, Inc." or fastivalle[0].get("address") != "1010 W 64th St" or fastivalle[0].get("startTime") != "19:00"):
            raise SystemExit(f"Fastivalle details are not durable in {path}")
        kingdom_choice = [event for event in rows if event.get("id") == KINGDOM_CHOICE_ID]
        if kingdom_choice and kingdom_choice[0].get("officialUrl") != KINGDOM_CHOICE_URL:
            raise SystemExit(f"Kingdom Choice ticket destination is not durable in {path}")
        by_id = {event.get("id"): event for event in rows}
        for retired_id, (canonical_id, doors, performance, venue_url) in ZAUNTEE_MERGES.items():
            canonical, retired = by_id.get(canonical_id), by_id.get(retired_id)
            if canonical and (canonical.get("doorsTime") != doors or canonical.get("performanceTime") != performance or "Skema Boy" not in canonical.get("artists", [])):
                raise SystemExit(f"Zauntee canonical merge is incomplete in {path}: {canonical_id}")
            if retired and (retired.get("status") != "merged" or retired.get("mergedIntoId") != canonical_id):
                raise SystemExit(f"Zauntee duplicate is not retired in {path}: {retired_id}")


def main() -> int:
    print(json.dumps(apply(), indent=2))
    check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
