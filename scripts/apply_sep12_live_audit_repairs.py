#!/usr/bin/env python3
"""Durable, source-backed repairs confirmed by the September 12, 2026 audit."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_EVENTS_FILE = ROOT / "supplemental-events.json"
MANUAL_EVENTS_FILE = ROOT / "config" / "manual-events.json"
EVENT_FILES = (
    EVENTS_FILE,
    SUPPLEMENTAL_EVENTS_FILE,
    MANUAL_EVENTS_FILE,
)
RARE_EVENTBRITE_ID = "1986268845586"
RARE_CANCEL_URL = "https://www.eventbrite.com/e/cancelled-rare-of-breed-tickets-1986268845586"
RARE_CANONICAL_ID = "eventbrite:rare-of-breed-jacksonville-2026"
FAITH_JAM_ID = "official:95cc80c13713dfecaf6d"
FAITH_JAM_URL = "https://www.eventbrite.com/e/faith-jam-2026-tickets-1985341605185"
MIKE_TEEZY_ID = "official:4e2fc5c7c02ab1d34b9e"
MIKE_TEEZY_URL = "https://music.apple.com/us/concerts/ce.01a1c61a-49a9-4e19-b629-46bac43b4970"
FASTIVALLE_ID = "official:ea0342f4771e9f9f1dfc"
FASTIVALLE_URL = "https://music.apple.com/us/concerts/ce.7570f0f7-b826-4400-a6f0-034778e98568"
KINGDOM_CHOICE_ID = "official:64bbcd477c3a36104df3"
KINGDOM_CHOICE_URL = "https://www.queenstheatre.org/events/kingdom-choice-awards-2026-dqr9"
ZAUNTEE_TOUR_IMAGE = "assets/artists/zauntee.webp"
ZAUNTEE_TOUR_IMAGE_SOURCE = "https://s1.ticketm.net/dam/e/54d/bad44a34-52c7-4dcd-b30b-d4906678154d_SOURCE"
ZAUNTEE_MERGES = {
    "supplemental:skema-boy-2026-11-01-new-york-ny": ("ticketmaster:k7vGF_CBswXt6", "17:00", "18:30", "https://mercuryeastpresents.com/tm-event/zauntee-god-remembers-tour/"),
    "supplemental:skema-boy-2026-11-08-atlanta-ga": ("ticketmaster:vvG1zZ_ClQMRrF", "19:00", "20:00", "https://www.masqueradeatlanta.com/events/zauntee/"),
    "supplemental:skema-boy-2026-11-19-los-angeles-ca": ("ticketmaster:vvG10Z_CMA3B0H", "21:30", "22:00", "https://themoroccan.com/tm-event/zauntee-god-remembers-tour/"),
}


def _is_zauntee_tour(event: dict) -> bool:
    artists = {str(name).casefold() for name in event.get("artists", [])}
    return (
        "god remembers tour" in str(event.get("title") or "").casefold()
        and {"zauntee", "skema boy"}.issubset(artists)
    )


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


def _is_rare(event: dict) -> bool:
    return (
        _normalized_id(event) == RARE_CANONICAL_ID
        or RARE_EVENTBRITE_ID in json.dumps(event, ensure_ascii=False)
    )


def _normalized_id(event: dict) -> str:
    return str(event.get("id") or "").removeprefix("manual:")


def authoritative_rare(rows: list[dict]) -> dict:
    """Return the single source-backed cancellation record or fail closed."""
    matches = [event for event in rows if _is_rare(event)]
    if len(matches) != 1:
        raise SystemExit(
            f"Expected exactly one authoritative Rare of Breed cancellation in {MANUAL_EVENTS_FILE}"
        )

    event = matches[0]
    valid_cancellation_source = any(
        isinstance(source, dict) and source.get("url") == RARE_CANCEL_URL
        for source in event.get("sources", [])
    )
    if (
        _normalized_id(event) != RARE_CANONICAL_ID
        or event.get("status") != "cancelled"
        or event.get("cancellationConfirmed") is not True
        or event.get("officialUrl") != RARE_CANCEL_URL
        or event.get("ticketUrl") != RARE_CANCEL_URL
        or not valid_cancellation_source
    ):
        raise SystemExit(
            f"Authoritative Rare of Breed cancellation is incomplete in {MANUAL_EVENTS_FILE}"
        )
    return event


def restore_generated_rare(rows: list[dict], source: dict) -> dict | None:
    """Restore the cancellation page record removed by the public-event collector."""
    if any(_is_rare(event) for event in rows):
        return None

    restored = deepcopy(source)
    restored["id"] = f"manual:{RARE_CANONICAL_ID}"
    restored_key = (
        str(restored.get("startDate") or "9999-12-31"),
        str(restored.get("startTime") or "23:59"),
        str(restored.get("title") or "").casefold(),
    )
    insert_at = next(
        (
            index
            for index, event in enumerate(rows)
            if (
                str(event.get("startDate") or "9999-12-31"),
                str(event.get("startTime") or "23:59"),
                str(event.get("title") or "").casefold(),
            )
            > restored_key
        ),
        len(rows),
    )
    rows.insert(insert_at, restored)
    return restored


def consolidate_rare(rows: list[dict]) -> tuple[dict | None, int]:
    """Collapse collector/source duplicates to one canonical Rare cancellation record.

    Full collection can rediscover the cancelled Jacksonville listing through more than
    one input. Keep the established manual/eventbrite identity when available, merge
    useful artist/source evidence, and remove duplicate rows before applying the
    cancellation state. This prevents the verified cancellation from failing a full
    refresh merely because the collector found the same event twice.
    """
    matches = [event for event in rows if _is_rare(event)]
    if not matches:
        return None, 0

    canonical = next(
        (event for event in matches if _normalized_id(event) == RARE_CANONICAL_ID),
        matches[0],
    )

    artists = list(canonical.get("artists") or [])
    seen_artists = {str(name).casefold() for name in artists}
    merged_ids = list(canonical.get("mergedIds") or [])
    for duplicate in matches:
        if duplicate is canonical:
            continue
        duplicate_id = duplicate.get("id")
        if duplicate_id and duplicate_id not in merged_ids:
            merged_ids.append(duplicate_id)
        for artist in duplicate.get("artists") or []:
            key = str(artist).casefold()
            if key not in seen_artists:
                artists.append(artist)
                seen_artists.add(key)
        for source in duplicate.get("sources") or []:
            if isinstance(source, dict) and source.get("url"):
                append_source(canonical, source)
        for key in ("image", "imageType", "imagePosition", "imageOverride", "venue", "address", "startTime", "timezone"):
            if not canonical.get(key) and duplicate.get(key):
                canonical[key] = duplicate[key]

    canonical["artists"] = artists
    if merged_ids:
        canonical["mergedIds"] = merged_ids
    rows[:] = [event for event in rows if event is canonical or not _is_rare(event)]
    return canonical, len(matches) - 1


def apply() -> dict[str, int]:
    report = {
        "cancelledRecords": 0,
        "rareDuplicatesCollapsed": 0,
        "rareRecordsRestored": 0,
        "faithJamRecords": 0,
        "mikeTeezyRecords": 0,
        "fastivalleRecords": 0,
        "kingdomChoiceRecords": 0,
        "zaunteeCanonicalRecords": 0,
        "zaunteeRetiredRecords": 0,
        "zaunteeTourImages": 0,
    }
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

    authoritative = authoritative_rare(load(MANUAL_EVENTS_FILE))

    for path in EVENT_FILES:
        rows = load(path)
        rare, collapsed = consolidate_rare(rows)
        changed = collapsed > 0
        report["rareDuplicatesCollapsed"] += collapsed

        if path == EVENTS_FILE and rare is None:
            rare = restore_generated_rare(rows, authoritative)
            if rare is not None:
                report["rareRecordsRestored"] += 1
                changed = True

        if rare:
            expected_id = f"manual:{RARE_CANONICAL_ID}" if path == EVENTS_FILE else RARE_CANONICAL_ID
            previous_id = rare.get("id")
            if previous_id and previous_id != expected_id:
                rare["mergedIds"] = list(dict.fromkeys([*rare.get("mergedIds", []), previous_id]))
            rare["id"] = expected_id
            rare["status"] = "cancelled"
            rare["cancellationConfirmed"] = True
            rare["cancellationConfirmedAt"] = "2026-09-12"
            rare["ticketAvailability"] = "cancelled"
            rare["officialUrl"] = RARE_CANCEL_URL
            rare["ticketUrl"] = RARE_CANCEL_URL
            rare["sourceName"] = "Official Eventbrite cancellation notice"
            rare["notes"] = "Cancelled by the organizer. This page is retained as a cancellation notice."
            append_source(rare, cancellation_source)
            report["cancelledRecords"] += 1
            changed = True

        by_id = {event.get("id"): event for event in rows}
        for event in rows:
            if _is_zauntee_tour(event):
                event["image"] = ZAUNTEE_TOUR_IMAGE
                event["imageType"] = "artist"
                event["imagePosition"] = "center"
                event["imageOverride"] = True
                event["imageSource"] = "Official Ticketmaster God Remembers Tour portrait"
                event["imageSourceUrl"] = ZAUNTEE_TOUR_IMAGE_SOURCE
                report["zaunteeTourImages"] += 1
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
        rare = [event for event in rows if _is_rare(event)]
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
        zauntee_tour = [event for event in rows if _is_zauntee_tour(event)]
        if zauntee_tour and not all(
            event.get("image") == ZAUNTEE_TOUR_IMAGE
            and event.get("imageType") == "artist"
            and event.get("imagePosition") == "center"
            and event.get("imageOverride") is True
            and event.get("imageSourceUrl") == ZAUNTEE_TOUR_IMAGE_SOURCE
            for event in zauntee_tour
        ):
            raise SystemExit(f"Zauntee tour image is not durable in {path}")


def main() -> int:
    print(json.dumps(apply(), indent=2))
    check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
