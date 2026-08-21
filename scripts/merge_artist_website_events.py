#!/usr/bin/env python3
"""Merge official-artist-website events into the production event catalog."""
from __future__ import annotations

from pathlib import Path

from update_events import (
    ARTISTS_FILE,
    ATTRACTION_CACHE_FILE,
    EVENTS_FILE,
    STATUS_FILE,
    apply_first_seen,
    artist_image_map,
    artist_image_positions,
    event_is_future,
    finalize_events,
    iso_z,
    load_json,
    merge_events,
    normalize_manual_event,
    now_utc,
    preferred_artist_images,
    write_json,
)

ROOT = Path(__file__).resolve().parents[1]
WEBSITE_EVENTS_FILE = ROOT / "artist-website-events.json"
SEED_EVENTS_FILE = ROOT / "config" / "artist-website-seed-events.json"


def main() -> int:
    checked_at = iso_z(now_utc())
    today = now_utc().date()

    existing = load_json(EVENTS_FILE, [])
    website_events = load_json(WEBSITE_EVENTS_FILE, [])
    seed_events = load_json(SEED_EVENTS_FILE, [])
    artists = load_json(ARTISTS_FILE, [])
    attraction_cache = load_json(ATTRACTION_CACHE_FILE, {})
    status = load_json(STATUS_FILE, {})

    if not isinstance(existing, list):
        existing = []
    if not isinstance(website_events, list):
        website_events = []
    if not isinstance(seed_events, list):
        seed_events = []
    if not isinstance(artists, list):
        artists = []
    if not isinstance(attraction_cache, dict):
        attraction_cache = {}
    if not isinstance(status, dict):
        status = {}

    normalized_seed = []
    for raw in seed_events:
        event = normalize_manual_event(raw, checked_at)
        if event:
            # These are official artist-calendar records, not editorial manual overrides.
            event["sourceAuthority"] = "artist_calendar"
            event["sourcePriority"] = 76
            for source in event.get("sources", []):
                if isinstance(source, dict):
                    source["authority"] = "artist_calendar"
                    source["priority"] = 76
            for evidence in event.get("artistEvidence", []):
                if isinstance(evidence, dict):
                    evidence["authority"] = "artist_calendar"
                    evidence["priority"] = 76
            normalized_seed.append(event)

    candidates = merge_events(
        event for event in [*existing, *website_events, *normalized_seed]
        if isinstance(event, dict) and event_is_future(event, today)
    )

    images = artist_image_map(artists, attraction_cache)
    positions = artist_image_positions(artists)
    prefer_artist = preferred_artist_images(artists)
    merged = finalize_events(candidates, images, today, positions, prefer_artist)
    merged = apply_first_seen(merged, existing, checked_at)
    write_json(EVENTS_FILE, merged)

    status["artistWebsiteEventsFound"] = len(website_events)
    status["artistWebsiteSeedEvents"] = len(normalized_seed)
    status["eventsPublished"] = len(merged)
    status["artistWebsiteMergeAt"] = checked_at
    write_json(STATUS_FILE, status)

    print(
        f"Merged official artist website events: dynamic={len(website_events)}, "
        f"seed={len(normalized_seed)}, published={len(merged)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
