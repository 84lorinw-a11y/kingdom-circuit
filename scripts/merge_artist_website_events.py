#!/usr/bin/env python3
"""Add official-artist-website events without reprocessing the live catalog."""
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
    events_are_duplicates,
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

    # Existing events.json is already finalized for public use. Never feed it back
    # through finalize_events(), because finalization intentionally strips internal
    # evidence fields and a second finalization would reject valid live events.
    #
    # Curated seed rows are also intentionally NOT passed through merge_events().
    # Each unique seed ID represents a separately verified performance. This matters
    # for school/church tours that can have multiple performances on the same date,
    # sometimes only an hour or two apart and linked from the same official tour page.
    dynamic_candidates = merge_events([
        event for event in website_events if isinstance(event, dict)
    ])
    images = artist_image_map(artists, attraction_cache)
    positions = artist_image_positions(artists)
    prefer_artist = preferred_artist_images(artists)

    finalized_dynamic = finalize_events(
        dynamic_candidates, images, today, positions, prefer_artist
    )
    finalized_seed = finalize_events(
        normalized_seed, images, today, positions, prefer_artist
    )
    finalized_dynamic = apply_first_seen(finalized_dynamic, existing, checked_at)
    finalized_seed = apply_first_seen(finalized_seed, existing, checked_at)

    merged = [dict(event) for event in existing if isinstance(event, dict)]
    added = 0

    # Verified seed IDs are authoritative. Preserve every unique seed performance,
    # but still allow one to collapse into a stronger non-seed listing when the
    # normal duplicate logic proves they are the same event.
    seed_ids = {str(event.get("id") or "") for event in finalized_seed if event.get("id")}
    for event in finalized_seed:
        event_id = str(event.get("id") or "")
        if event_id and any(str(current.get("id") or "") == event_id for current in merged):
            continue
        non_seed_existing = [
            current for current in merged
            if str(current.get("id") or "") not in seed_ids
        ]
        if any(events_are_duplicates(current, event) for current in non_seed_existing):
            continue
        merged.append(event)
        added += 1

    # Dynamically discovered website events use the standard duplicate rules.
    for event in finalized_dynamic:
        if any(events_are_duplicates(current, event) for current in merged):
            continue
        merged.append(event)
        added += 1

    merged.sort(key=lambda item: (
        str(item.get("startDate") or "9999-12-31"),
        str(item.get("startTime") or "23:59"),
        str(item.get("title") or "").casefold(),
    ))

    if len(merged) < len(existing):
        raise SystemExit(
            f"Website merge is destructive: before={len(existing)} after={len(merged)}"
        )

    present_ids = {str(event.get("id") or "") for event in merged}
    missing_seed_ids = sorted(seed_ids - present_ids)
    if missing_seed_ids:
        raise SystemExit(
            f"Verified artist seed performances were lost during merge: {missing_seed_ids}"
        )

    write_json(EVENTS_FILE, merged)
    status["artistWebsiteEventsFound"] = len(website_events)
    status["artistWebsiteSeedEvents"] = len(normalized_seed)
    status["artistWebsiteEventsAdded"] = added
    status["eventsPublished"] = len(merged)
    status["artistWebsiteMergeAt"] = checked_at
    write_json(STATUS_FILE, status)

    print(
        f"Added official artist website events: dynamic={len(website_events)}, "
        f"seed={len(normalized_seed)}, added={added}, before={len(existing)}, after={len(merged)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
