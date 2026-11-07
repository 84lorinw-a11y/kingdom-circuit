#!/usr/bin/env python3
"""Run Bandsintown refresh without self-deduping previously published BIT rows.

The underlying collector correctly dedupes Bandsintown against the main catalog and
non-Bandsintown supplemental events. Previously, however, it also compared fresh
Bandsintown rows against its own prior output, then replaced those prior rows with
an empty result. This wrapper removes prior Bandsintown-generated rows only for the
comparison phase, runs the collector, and retains established upcoming US/CA
bookings omitted by the provider. Absence alone is review evidence, not proof of
cancellation; exact replacements and existing editorial exclusions still win.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit
from canadian_event_guard import is_canadian, today_cutoff
from catalog_removals import removed_event
from apply_curated_catalog_policy import EXCLUDED_ARTISTS, curate_event, is_known_duplicate_fragment

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
    if event.get("holdReason") or norm(event.get("status")) in {
        "cancelled", "canceled", "postponed", "merged", "held", "hold", "removed"
    }:
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


def exact_identities(event: dict) -> set[str]:
    """Only durable IDs/provider links prove that another row replaces this one."""
    aliases = event.get("mergedFromIds") or []
    identifiers = {str(value) for value in [event.get("id"), *(aliases if isinstance(aliases, list) else [])] if value}
    for value in list(identifiers):
        if value.startswith("manual:bandsintown:"):
            identifiers.add(value.removeprefix("manual:"))
    if event.get("bandsintownEventId"):
        identifiers.add("bandsintown:" + str(event["bandsintownEventId"]))
    sources = event.get("sources") or []
    urls = [event.get("officialUrl"), event.get("ticketUrl"),
            *(source.get("url") for source in sources if isinstance(source, dict))]
    for value in urls:
        try:
            url = urlsplit(str(value or ""))
            match = re.fullmatch(r"/[et]/(\d+)(?:-[^/]+)?/?", url.path)
            if url.scheme in {"http", "https"} and (url.hostname or "").lower() in {"bandsintown.com", "www.bandsintown.com"} and match:
                identifiers.add("bandsintown:" + match[1])
        except ValueError:
            continue
    return identifiers


def retained_missing(event: dict, cutoff: str, disabled: set[str], country_code) -> dict | None:
    """Keep eligible source facts while applying existing editorial exclusions."""
    if country_code(event.get("country")) not in {"US", "CA"}:
        return None
    if removed_event(event) or is_known_duplicate_fragment(event):
        return None
    owner = event.get("trackedArtist") or event.get("headliner")
    owners = [owner] if owner else event.get("artists", [])
    if any(norm(name) in disabled for name in owners) or event.get("holdReason"):
        return None
    if norm(event.get("status")) in {"cancelled", "canceled", "postponed", "merged", "held", "hold", "removed"}:
        return None
    retained = curate_event(event)
    if retained is None:
        return None
    excluded = disabled | EXCLUDED_ARTISTS
    for field in ("artists", "advertisedBilling", "officialBill"):
        if field in retained:
            retained[field] = [name for name in retained[field] if norm(name) not in excluded]
    if not retained["artists"]:
        return None
    if norm(retained.get("headliner")) in excluded:
        retained["headliner"] = retained["artists"][0]
    try:
        start = date.fromisoformat(str(event.get("startDate") or "")[:10])
    except ValueError:
        return None
    try:
        end = date.fromisoformat(str(event.get("endDate") or "")[:10])
    except ValueError:
        end = start
    return retained if max(start, end).isoformat() >= cutoff else None


def read_rows(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"Expected an array of objects: {path.name}")
    return rows


def main() -> int:
    original_bytes = SUPPLEMENTAL.read_bytes()
    original = read_rows(SUPPLEMENTAL)
    original_status = STATUS.read_bytes() if STATUS.exists() else None
    sys.path.insert(0, str(ROOT / "scripts"))
    import collect_bandsintown_rest as collector  # type: ignore

    primary = read_rows(collector.EVENTS_FILE)
    roster = read_rows(collector.ARTISTS_FILE)
    disabled = {norm(name) for artist in roster if artist.get("enabled", True) is False
                for name in [artist.get("name"), *(artist.get("aliases") or [])] if name}
    prior_bit = [event for event in original if is_refreshable_bit(event)]
    non_bit = [event for event in original if not is_refreshable_bit(event)]
    started = datetime.now(timezone.utc)
    try:
        # Prior BIT rows must not self-dedupe. Requiring a newly written receipt
        # also prevents old request errors from being mistaken for this pass.
        save(SUPPLEMENTAL, non_bit)
        STATUS.unlink(missing_ok=True)
        result = int(collector.main())
        if result != 0:
            raise RuntimeError(f"collector returned {result}")
        refreshed = read_rows(SUPPLEMENTAL)
        status = json.loads(STATUS.read_text(encoding="utf-8"))
        if not isinstance(status, dict) or not isinstance(status.get("errors"), list) or not all(isinstance(item, dict) for item in status["errors"]):
            raise ValueError("Bandsintown refresh produced an invalid status")
        expected_artists = sum(artist.get("enabled", True) is not False and bool(artist.get("name")) for artist in roster)
        if (type(status.get("artistsChecked")) is not int or status["artistsChecked"] != expected_artists
                or type(status.get("requestErrors")) is not int or status["requestErrors"] < len(status["errors"])):
            raise ValueError("Bandsintown refresh produced an incomplete status")
        generated = datetime.fromisoformat(str(status.get("generatedAt") or "").replace("Z", "+00:00"))
        if generated.tzinfo is None or not started <= generated <= datetime.now(timezone.utc):
            raise ValueError("Bandsintown refresh did not produce a current status")

        protected = set().union(*(exact_identities(event) for event in [*non_bit, *primary]))
        fresh_bit = [event for event in refreshed if is_refreshable_bit(event) and not exact_identities(event) & protected]
        # The collector only adds provider-owned rows. Restore the original
        # protected records, including holds its older filter does not recognize.
        fresh_non_bit = non_bit
        preserve_canadian_details(fresh_bit, prior_bit)
        curated_images_preserved = preserve_curated_image_overrides(fresh_bit, prior_bit)
        replacements = set().union(*(exact_identities(event) for event in [*refreshed, *primary]))
        cutoff = today_cutoff()
        preserved = []
        for event in prior_bit:
            if not exact_identities(event) & replacements:
                retained = retained_missing(event, cutoff, disabled, collector.country_code)
                if retained is not None:
                    preserved.append(retained)
        failed_artists = {norm(item.get("artist")) for item in status["errors"] if item.get("artist")}
        merged = [*fresh_non_bit, *fresh_bit, *preserved]
        merged.sort(key=lambda event: (str(event.get("startDate") or "9999-12-31"), str(event.get("title") or "")))
        save(SUPPLEMENTAL, merged)

        status["activeNonFestivalBandsintownShows"] = len(fresh_bit) + len(preserved)
        status["priorBandsintownShows"] = len(prior_bit)
        status["preservedDueToRequestErrors"] = sum(
            norm(event.get("trackedArtist") or event.get("headliner")) in failed_artists for event in preserved)
        status["preservedCanadianShows"] = sum(is_canadian(event) for event in preserved)
        status["curatedImageOverridesPreserved"] = curated_images_preserved
        status["missingProviderShowsRetained"] = len(preserved)
        status["missingProviderReview"] = [
            {"id": event["id"], "officialUrl": event.get("officialUrl") or "",
             "reason": "absent_from_current_provider_output_not_confirmed_cancelled"}
            for event in preserved]
        save(STATUS, status)
    except (Exception, SystemExit):
        SUPPLEMENTAL.write_bytes(original_bytes)
        if original_status is None:
            STATUS.unlink(missing_ok=True)
        else:
            STATUS.write_bytes(original_status)
        raise

    print("Bandsintown refresh safeguard: "
          f"prior={len(prior_bit)}, fresh={len(fresh_bit)}, missing_for_review={len(preserved)}, "
          f"preserved_on_error={status['preservedDueToRequestErrors']}, "
          f"preserved_canadian={status['preservedCanadianShows']}, curated_images={curated_images_preserved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
