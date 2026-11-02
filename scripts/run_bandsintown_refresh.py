#!/usr/bin/env python3
"""Run Bandsintown refresh without self-deduping previously published BIT rows.

The underlying collector correctly dedupes Bandsintown against the main catalog and
non-Bandsintown supplemental events. Previously, however, it also compared fresh
Bandsintown rows against its own prior output, then replaced those prior rows with
an empty result. This wrapper removes prior Bandsintown-generated rows only for the
comparison phase, runs the collector, and preserves prior rows for artists whose
Bandsintown request explicitly failed during this run. Canadian bookings also
survive missing provider results; absence alone is not cancellation evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from canadian_event_guard import is_canadian

ROOT = Path(__file__).resolve().parents[1]
SUPPLEMENTAL = ROOT / "supplemental-events.json"
STATUS = ROOT / "bandsintown-status.json"
CURATED_IMAGE_FIELDS = (
    "image",
    "imageType",
    "imagePosition",
    "imageOverride",
    "imageSource",
    "imageSourceUrl",
    "auditVerified",
)


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def norm(value) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def is_refreshable_bit(event) -> bool:
    """Return whether Bandsintown still owns the canonical event record.

    Some records retain a Bandsintown ID after official details replace the
    provider payload. Those higher-authority records must survive refreshes.
    """
    if not isinstance(event, dict) or not str(event.get("id") or "").startswith("bandsintown:"):
        return False
    # Explicit editorial cancellations and official records are never revived
    # by a provider's still-scheduled listing.
    if norm(event.get("status")) in {"cancelled", "canceled", "postponed", "merged"}:
        return False
    return norm(event.get("authority")) in {"", "artist_calendar"}


def preserve_curated_image_overrides(
    fresh_events: list[dict], prior_events: list[dict]
) -> int:
    """Carry intentional artwork/crop overrides across provider refreshes."""
    prior_by_id = {
        str(event.get("id") or ""): event
        for event in prior_events
        if isinstance(event, dict) and event.get("id")
    }
    preserved = 0
    for event in fresh_events:
        prior = prior_by_id.get(str(event.get("id") or ""))
        if not prior or prior.get("imageOverride") is not True:
            continue
        changed = False
        for field in CURATED_IMAGE_FIELDS:
            if field in prior and event.get(field) != prior[field]:
                event[field] = prior[field]
                changed = True
        preserved += int(changed)
    return preserved


def preserve_canadian_details(fresh_events: list[dict], prior_events: list[dict]) -> None:
    """Do not shorten known multi-day bookings when the API omits their end."""
    prior_by_id = {event.get("id"): event for event in prior_events if is_canadian(event)}
    for event in fresh_events:
        prior = prior_by_id.get(event.get("id"))
        if not prior or not is_canadian(event):
            continue
        if prior.get("startDate") == event.get("startDate"):
            for field in ("endDate", "endDateTime"):
                if prior.get(field) and not event.get(field):
                    event[field] = prior[field]
        if all(norm(prior.get(key)) == norm(event.get(key)) for key in ("city", "state")):
            if prior.get("timezone") and not event.get("timezone"):
                event["timezone"] = prior["timezone"]
            if all(prior.get(key) == event.get(key) for key in ("startDate", "startTime")):
                if prior.get("startDateTime") and not event.get("startDateTime"):
                    event["startDateTime"] = prior["startDateTime"]


def main() -> int:
    original = load(SUPPLEMENTAL, [])
    if not isinstance(original, list):
        raise SystemExit("supplemental-events.json must be an array")

    prior_bit = [event for event in original if is_refreshable_bit(event)]
    non_bit = [event for event in original if not is_refreshable_bit(event)]

    # Critical: the collector must not see its own previous Bandsintown rows while
    # deciding whether a fresh Bandsintown event duplicates the established catalog.
    save(SUPPLEMENTAL, non_bit)

    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import collect_bandsintown_rest  # type: ignore

        result = int(collect_bandsintown_rest.main())
        if result != 0:
            raise RuntimeError(f"collector returned {result}")
    except Exception:
        # Never leave the working tree with a destructive partial refresh.
        save(SUPPLEMENTAL, original)
        raise

    refreshed = load(SUPPLEMENTAL, [])
    status = load(STATUS, {})
    if not isinstance(refreshed, list) or not isinstance(status, dict):
        save(SUPPLEMENTAL, original)
        raise SystemExit("Bandsintown refresh produced invalid output")

    fresh_bit = [event for event in refreshed if is_refreshable_bit(event)]
    fresh_non_bit = [event for event in refreshed if not is_refreshable_bit(event)]
    preserve_canadian_details(fresh_bit, prior_bit)
    curated_images_preserved = preserve_curated_image_overrides(fresh_bit, prior_bit)

    # If a specific artist's request failed, keep that artist's last known rows for
    # this run rather than deleting valid shows because of a transient API problem.
    failed_artists = {
        norm(item.get("artist"))
        for item in status.get("errors", [])
        if isinstance(item, dict) and item.get("artist")
    }
    fresh_ids = {
        str(identifier)
        for event in refreshed
        for identifier in [event.get("id") or "", *event.get("mergedFromIds", [])]
    }
    preserved = [
        event for event in prior_bit
        if (is_canadian(event) or norm(event.get("trackedArtist") or event.get("headliner")) in failed_artists)
        and str(event.get("id") or "") not in fresh_ids
    ]

    merged = [*fresh_non_bit, *fresh_bit, *preserved]
    merged.sort(key=lambda event: (str(event.get("startDate") or "9999-12-31"), str(event.get("title") or "")))
    save(SUPPLEMENTAL, merged)

    status["activeNonFestivalBandsintownShows"] = len(fresh_bit) + len(preserved)
    status["priorBandsintownShows"] = len(prior_bit)
    status["preservedDueToRequestErrors"] = sum(
        norm(event.get("trackedArtist") or event.get("headliner")) in failed_artists
        for event in preserved
    )
    status["preservedCanadianShows"] = sum(is_canadian(event) for event in preserved)
    status["curatedImageOverridesPreserved"] = curated_images_preserved
    save(STATUS, status)

    print(
        "Bandsintown refresh safeguard: "
        f"prior={len(prior_bit)}, fresh={len(fresh_bit)}, "
        f"preserved_on_error={status['preservedDueToRequestErrors']}, "
        f"preserved_canadian={status['preservedCanadianShows']}, curated_images={curated_images_preserved}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
