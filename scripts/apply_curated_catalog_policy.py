#!/usr/bin/env python3
"""Apply durable editorial decisions and coverage-gap monitoring.

This runs in CI after collection (or directly before a push build) so verified
editorial decisions cannot be undone by an automated source refresh. It also
records source-redundancy gaps so a priority artist is not silently dependent
on a single fragile calendar.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POLICY_VERSION = 3
ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
OFFICIAL_SOURCES_FILE = ROOT / "config" / "official-sources.json"
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"
RUN_STATUS_FILE = ROOT / "run-status.json"
COVERAGE_GAPS_FILE = ROOT / "coverage-gaps.json"

EXCLUDED_ARTISTS = {"madison ryann ward"}

MIKE_TEEZY_HRVSTLAND = {
    "id": "mike-teezy-hrvstland-festival-2026",
    "title": "HRVSTLAND Festival 2026",
    "startDate": "2026-10-24",
    "startTime": "",
    "venue": "Steele Creek Church",
    "address": "",
    "city": "Charlotte",
    "state": "NC",
    "artists": ["Mike Teezy"],
    "headliner": "Mike Teezy",
    "eventType": "festival",
    "ticketUrl": "https://www.bandsintown.com/f/231374",
    "officialUrl": "https://www.bandsintown.com/f/231374",
    "image": "",
    "price": "",
    "status": "scheduled",
    "lineupExplicit": True,
    "authority": "artist_calendar",
    "sourceName": "Mike Teezy verified Bandsintown / HRVSTLAND listing",
}

ARK_ARTISTS = ["Zauntee", "Scootie Wop", "Dante' Pride", "Anike", "Y Shadey"]
ARK_OF_WORSHIP = {
    "id": "ark-of-worship-2026",
    "title": "Ark of Worship Gospel & Christian Music Festival 2026",
    "startDate": "2026-10-09",
    "endDate": "2026-10-10",
    "startTime": "",
    "venue": "Southwest Trail Riders Association Property",
    "address": "13711 Almeda School Rd",
    "city": "Houston",
    "state": "TX",
    "artists": ARK_ARTISTS,
    "headliner": "Zauntee",
    "eventType": "festival",
    "ticketUrl": "https://www.arkofworship.com/tickets",
    "officialUrl": "https://www.arkofworship.com/lineup",
    "image": "",
    "price": "$59+ single-day / $99+ 2-day",
    "status": "scheduled",
    "lineupExplicit": True,
    "authority": "official_festival",
    "sourceName": "Ark of Worship official festival lineup",
}

NICKY_UNRESOLVED = {
    "artist": "Nicky Gracious",
    "title": "YOU ARE NOT FORGOTTEN",
    "startDate": "2026-10-03",
    "officialUrl": "https://nickygraciousmusic.com/products/you-are-not-forgotten-saturday-october-3rd",
    "status": "confirmed_date_missing_location",
    "publish": False,
    "reason": "Official artist page confirms the October 3, 2026 show but does not publish a venue, city, or state yet.",
}


def load(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def curate_event(event: dict[str, Any]) -> dict[str, Any] | None:
    artists = [
        artist for artist in event.get("artists", [])
        if norm(artist) not in EXCLUDED_ARTISTS
    ]
    if not artists:
        return None

    updated = dict(event)
    updated["artists"] = artists
    if norm(updated.get("headliner")) in EXCLUDED_ARTISTS:
        updated["headliner"] = artists[0]
    return updated


def is_ark_fragment(event: dict[str, Any]) -> bool:
    if norm(event.get("id")) == norm(ARK_OF_WORSHIP["id"]):
        return False
    if str(event.get("startDate") or "") not in {"2026-10-09", "2026-10-10"}:
        return False
    if norm(event.get("city")) != "houston" or norm(event.get("state")) != "tx":
        return False
    location = f"{event.get('venue', '')} {event.get('address', '')}".casefold()
    same_site = "southwest trail riders" in location or "13711 almeda school" in location
    event_artists = {norm(name) for name in event.get("artists", [])}
    ark_artists = {norm(name) for name in ARK_ARTISTS}
    return same_site and bool(event_artists & ark_artists)


def source_is_dedicated_artist_calendar(source: dict[str, Any], artist_key: str) -> bool:
    """Return True only for sources dedicated to one artist, not festival appearances."""
    if norm(source.get("artist")) == artist_key:
        return True
    configured = [norm(name) for name in source.get("artists", []) if norm(name)]
    authority = norm(source.get("authority"))
    return len(configured) == 1 and configured[0] == artist_key and authority in {"artist_calendar", "artist_label"}


def build_coverage_report(
    artists: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    run_status: dict[str, Any],
) -> dict[str, Any]:
    result_by_name = {
        str(item.get("name") or ""): item
        for item in run_status.get("sourceResults", [])
        if isinstance(item, dict)
    }
    unmatched = {norm(name) for name in run_status.get("unmatchedArtists", [])}
    ticketmaster_warnings = {
        norm(str(item).split(":", 1)[0].removeprefix("Ticketmaster - "))
        for item in run_status.get("warnings", [])
        if str(item).startswith("Ticketmaster - ")
    }

    high_risk: list[dict[str, Any]] = []
    medium_risk: list[dict[str, Any]] = []

    for artist in artists:
        if not isinstance(artist, dict) or not artist.get("enabled", True):
            continue
        if int(artist.get("monitoringPriority") or 3) != 1:
            continue
        name = str(artist.get("name") or "").strip()
        key = norm(name)
        dedicated = [
            source for source in sources
            if isinstance(source, dict)
            and source.get("enabled", True)
            and source_is_dedicated_artist_calendar(source, key)
        ]
        failed_sources = [
            str(source.get("name") or source.get("url") or "Official source")
            for source in dedicated
            if result_by_name.get(str(source.get("name") or source.get("url") or "Official source"), {}).get("status") == "warning"
        ]
        healthy_sources = [
            str(source.get("name") or source.get("url") or "Official source")
            for source in dedicated
            if result_by_name.get(str(source.get("name") or source.get("url") or "Official source"), {}).get("status") == "ok"
        ]
        tm_enabled = bool(artist.get("ticketmasterEnabled", True))
        tm_unmatched = tm_enabled and key in unmatched
        tm_failed = tm_enabled and key in ticketmaster_warnings

        record = {
            "artist": name,
            "healthyDedicatedSources": healthy_sources,
            "failedDedicatedSources": failed_sources,
            "ticketmasterUnmatched": tm_unmatched,
            "ticketmasterFailed": tm_failed,
        }
        if failed_sources and not healthy_sources and (tm_unmatched or tm_failed):
            record["reason"] = "Every dedicated artist calendar failed and Ticketmaster did not provide a reliable fallback."
            high_risk.append(record)
        elif tm_unmatched and not healthy_sources:
            record["reason"] = "No Ticketmaster match and no healthy dedicated artist calendar was recorded in the latest run."
            medium_risk.append(record)
        elif failed_sources:
            record["reason"] = "At least one dedicated artist source failed, but another artist calendar or Ticketmaster channel remains available."
            medium_risk.append(record)

    return {
        "policyVersion": POLICY_VERSION,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "highRiskArtists": high_risk,
        "mediumRiskArtists": medium_risk,
        "incompleteConfirmedEvents": [NICKY_UNRESOLVED],
        "notes": [
            "High risk means every dedicated priority-artist calendar failed and Ticketmaster is also unavailable or unmatched.",
            "Medium risk means coverage is degraded but at least one useful channel may remain, or no dedicated artist calendar is currently healthy.",
            "Incomplete confirmed events stay off the public calendar until a venue/city/state can be verified.",
        ],
    }


def main() -> int:
    artists = load(ARTISTS_FILE, [])
    sources = load(OFFICIAL_SOURCES_FILE, [])
    events = load(EVENTS_FILE, [])
    supplemental = load(SUPPLEMENTAL_FILE, [])
    run_status = load(RUN_STATUS_FILE, {})

    if not isinstance(artists, list) or not isinstance(events, list) or not isinstance(supplemental, list):
        raise SystemExit("Curated catalog policy expected JSON arrays")
    if not isinstance(sources, list):
        sources = []
    if not isinstance(run_status, dict):
        run_status = {}

    found_madison = False
    for artist in artists:
        if not isinstance(artist, dict) or norm(artist.get("name")) != "madison ryann ward":
            continue
        found_madison = True
        artist["enabled"] = False
        artist["ticketmasterEnabled"] = False
        artist["socialSearchEnabled"] = False
        artist["textMatchEnabled"] = False
        artist["activeStatus"] = "excluded_non_chh"
        artist["editorialNote"] = "Excluded from Kingdom Circuit: not Christian hip-hop."

    if not found_madison:
        raise SystemExit("Madison Ryann Ward roster entry was not found")

    curated_events: list[dict[str, Any]] = []
    removed_madison_events = 0
    removed_ark_fragments = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        curated = curate_event(event)
        if curated is None:
            removed_madison_events += 1
            continue
        if is_ark_fragment(curated):
            removed_ark_fragments += 1
            continue
        curated_events.append(curated)

    curated_supplemental: list[dict[str, Any]] = []
    target_ids = {norm(MIKE_TEEZY_HRVSTLAND["id"]), norm(ARK_OF_WORSHIP["id"])}
    for event in supplemental:
        if not isinstance(event, dict):
            continue
        curated = curate_event(event)
        if curated is None or is_ark_fragment(curated):
            continue
        if norm(curated.get("id")) in target_ids:
            continue
        curated_supplemental.append(curated)

    curated_supplemental.extend([MIKE_TEEZY_HRVSTLAND, ARK_OF_WORSHIP])
    curated_supplemental.sort(
        key=lambda event: (str(event.get("startDate") or "9999-12-31"), norm(event.get("title")))
    )

    coverage_report = build_coverage_report(artists, sources, run_status)

    write(ARTISTS_FILE, artists)
    write(EVENTS_FILE, curated_events)
    write(SUPPLEMENTAL_FILE, curated_supplemental)
    write(COVERAGE_GAPS_FILE, coverage_report)

    enabled_names = {
        norm(artist.get("name"))
        for artist in artists
        if isinstance(artist, dict) and artist.get("enabled", True)
    }
    if "madison ryann ward" in enabled_names:
        raise SystemExit("Madison Ryann Ward is still enabled")

    all_published = [*curated_events, *curated_supplemental]
    if any("madison ryann ward" in {norm(name) for name in event.get("artists", [])} for event in all_published):
        raise SystemExit("Madison Ryann Ward still appears in published event data")
    if any(is_ark_fragment(event) for event in all_published):
        raise SystemExit("Ark of Worship still has split individual event fragments")
    if not any(norm(event.get("id")) == norm(ARK_OF_WORSHIP["id"]) for event in curated_supplemental):
        raise SystemExit("Ark of Worship canonical festival event was not injected")
    if not any(norm(event.get("id")) == norm(MIKE_TEEZY_HRVSTLAND["id"]) for event in curated_supplemental):
        raise SystemExit("Mike Teezy HRVSTLAND event was not injected")

    print(
        f"Curated catalog policy v{POLICY_VERSION} applied: Madison disabled; "
        f"{removed_madison_events} Madison-only event(s) removed; "
        f"{removed_ark_fragments} Ark fragment(s) consolidated; "
        "Mike Teezy HRVSTLAND and Ark of Worship ensured."
    )
    print(
        "Coverage audit: "
        f"{len(coverage_report['highRiskArtists'])} high-risk priority artist(s), "
        f"{len(coverage_report['mediumRiskArtists'])} medium-risk priority artist(s), "
        f"{len(coverage_report['incompleteConfirmedEvents'])} incomplete confirmed event(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
