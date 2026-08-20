#!/usr/bin/env python3
"""Apply durable, verified editorial corrections for artist images and tour lineups."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
EVENTS_FILE = ROOT / "events.json"
SUPPLEMENTAL_FILE = ROOT / "supplemental-events.json"

CALEB_IMAGE = "https://tprlive.co/cdn/shop/files/ARTIST_HEADSHOT_36.jpg?v=1776887171&width=1797"
CALEB_SOURCE = "https://tprlive.co/collections/caleb-gordon-the-eden-experience"

HOPE_FEST_IMAGE = "https://images.sk-static.com/images/media/profile_images/events/43075130/huge_avatar?series_id=719039"
HOPE_FEST_IMAGE_SOURCE = "https://www.songkick.com/festivals/719039-hope-fest/id/43075130-hope-fest-2026"

INDIE_TOUR_STOPS = {
    ("2026-08-22", "Los Angeles"): ("The Novo official calendar", "https://www.thenovodtla.com/events"),
    ("2026-09-03", "Orlando"): ("AXS", "https://www.axs.com/events/1398557/hulvey-tickets"),
    ("2026-09-04", "Miami Beach"): ("AXS", "https://www.axs.com/events/1394626/hulvey-tickets"),
    ("2026-09-05", "Jacksonville"): ("Bandsintown", "https://www.bandsintown.com/e/108188682-hulvey-at-five?came_from=287"),
    ("2026-09-20", "Minneapolis"): ("First Avenue", "https://first-avenue.com/event/2026-09-hulvey/"),
    ("2026-09-22", "Grand Rapids"): ("The Intersection", "https://sectionlive.com/events/"),
    ("2026-09-23", "Indianapolis"): ("HI-FI Indy", "https://hifiindy.com/event/hulvey-2026/"),
}


def norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def add_source(event: dict[str, Any], name: str, url: str) -> None:
    sources = list(event.get("sources") or [])
    if not any(str(item.get("url") or "").rstrip("/") == url.rstrip("/") for item in sources if isinstance(item, dict)):
        sources.append({
            "name": name,
            "url": url,
            "type": "manual_verified",
            "authority": "venue_ticket",
            "priority": 100,
        })
    event["sources"] = sources


def main() -> int:
    artists = load(ARTISTS_FILE)
    events = load(EVENTS_FILE)
    supplemental = load(SUPPLEMENTAL_FILE)
    if not isinstance(artists, list) or not isinstance(events, list) or not isinstance(supplemental, list):
        raise SystemExit("Expected artist/event JSON arrays")

    # Caleb Gordon: use a stable, official TPR portrait instead of the flaky external fallback.
    caleb = next((item for item in artists if norm(item.get("name")) == "caleb gordon"), None)
    if not caleb:
        raise SystemExit("Caleb Gordon missing from artist registry")
    caleb["imageUrl"] = CALEB_IMAGE
    caleb["imagePosition"] = "center"
    caleb["preferArtistImage"] = True
    caleb["sourceRegistryVerified"] = True
    caleb["officialImageSource"] = CALEB_SOURCE

    all_events = [*events, *supplemental]

    # Hope Fest: replace the KC-made placeholder art with the event-specific listing image.
    hope_matches = []
    for event in all_events:
        if (
            str(event.get("startDate") or "") == "2026-08-22"
            and norm(event.get("city")) == "daytona beach"
            and "hope fest" in norm(event.get("title"))
        ):
            event["image"] = HOPE_FEST_IMAGE
            event["imageType"] = "event_artwork"
            event["imagePosition"] = "center"
            event["imageOverride"] = True
            event["imageSource"] = HOPE_FEST_IMAGE_SOURCE
            hope_matches.append(event)
    if not hope_matches:
        raise SystemExit("Hope Fest 2026 record not found")

    # Seven existing Hulvey dates were missing the verified tour support artists.
    found_stops: set[tuple[str, str]] = set()
    for event in all_events:
        key = (str(event.get("startDate") or ""), str(event.get("city") or ""))
        if key not in INDIE_TOUR_STOPS:
            continue
        if "hulvey" not in {norm(a) for a in event.get("artists", [])} and "hulvey" not in norm(event.get("title")):
            continue

        names = list(event.get("artists") or [])
        normalized = {norm(name) for name in names}
        if "indie tribe." not in normalized and "indie tribe" not in normalized:
            names.append("indie tribe.")
        if "kijan boone" not in normalized:
            names.append("Kijan Boone")
        event["artists"] = names
        event["lineupExplicit"] = True
        source_name, source_url = INDIE_TOUR_STOPS[key]
        add_source(event, source_name, source_url)
        found_stops.add(key)

    missing = sorted(set(INDIE_TOUR_STOPS) - found_stops)
    if missing:
        raise SystemExit(f"Verified indie tribe tour stops missing from dataset: {missing}")

    # Guard against broad tour listings incorrectly tagging festival/special-event dates.
    for event in all_events:
        if str(event.get("startDate") or "") in {"2026-09-11", "2026-09-12"}:
            if norm(event.get("city")) in {"saratoga springs", "shippensburg"}:
                if "indie tribe." in {norm(a) for a in event.get("artists", [])}:
                    raise SystemExit(f"Unexpected indie tribe assignment on special-event date: {event.get('id')}")

    write(ARTISTS_FILE, artists)
    write(EVENTS_FILE, events)
    write(SUPPLEMENTAL_FILE, supplemental)

    # Final validation.
    assert caleb.get("imageUrl") == CALEB_IMAGE
    assert all(item.get("image") == HOPE_FEST_IMAGE for item in hope_matches)
    for key in INDIE_TOUR_STOPS:
        matched = [
            e for e in all_events
            if (str(e.get("startDate") or ""), str(e.get("city") or "")) == key
            and ("hulvey" in {norm(a) for a in e.get("artists", [])} or "hulvey" in norm(e.get("title")))
        ]
        assert matched, key
        assert all("indie tribe." in {norm(a) for a in e.get("artists", [])} for e in matched), key
        assert all("kijan boone" in {norm(a) for a in e.get("artists", [])} for e in matched), key

    print(
        f"Verified content overrides applied: Caleb portrait fixed; Hope Fest artwork replaced; "
        f"{len(found_stops)} indie tribe tour stops normalized."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
