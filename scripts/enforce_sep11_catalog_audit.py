#!/usr/bin/env python3
"""Enforce the Sep. 11 catalog audit without shifting the canonical artist roster.

Madison Ryann Ward stays as a disabled tombstone so roster positions remain
stable, while all event associations are removed and automated tracking stays
off. The underlying audit script remains authoritative for event additions and
lineup repairs.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import apply_sep11_catalog_audit as audit

ROOT = Path(__file__).resolve().parents[1]
ARTISTS_FILE = ROOT / "config" / "artists.json"
BLOCKED = "madison ryann ward"
FALLBACK_ROSTER_ORDER = 28

VERIFIED_EVENT_IMAGES = {
    "fountain-fest-wv-2026": (
        "https://i0.wp.com/fountainfestwv.com/wp-content/uploads/2026/07/Rare-of-Breed-Promo-.webp?resize=720%2C900&ssl=1",
        "artist",
    ),
    "jay-kalyl-desde-antes-rockville-centre-2026": ("assets/events/jay-kalyl-desde-antes-2026.svg", "event_artwork"),
    "mayia-boxyard-saturdaze-2026": ("assets/events/mayia-boxyard-saturdaze-2026.svg", "event_artwork"),
    "mayia-nc-state-fair-2026": ("assets/events/mayia-nc-state-fair-2026.svg", "event_artwork"),
    "mission-friends-sacramento-2026": ("assets/events/mission-friends-sacramento-2026.svg", "event_artwork"),
    "alex-zurdo-zona-zero-san-juan-2026": ("assets/events/alex-zurdo-zona-zero-2026.svg", "event_artwork"),
    "cj-emulous-kickback-grand-prairie-2026": ("assets/events/cj-emulous-kickback-2026.svg", "event_artwork"),
    "miles-cj-zion-ultra-lounge-chandler-2026": ("assets/events/miles-cj-zion-ultra-2026.svg", "event_artwork"),
}


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def load_artists() -> list[dict]:
    return json.loads(ARTISTS_FILE.read_text(encoding="utf-8"))


def save_artists(items: list[dict]) -> None:
    ARTISTS_FILE.write_text(
        json.dumps(items, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def excluded_tombstone(template: dict | None, roster_order: int) -> dict:
    item = deepcopy(template or {
        "name": "Madison Ryann Ward",
        "aliases": ["Madison Ryann Ward"],
        "category": "crossover",
        "monitoringPriority": 3,
    })
    item["name"] = "Madison Ryann Ward"
    item["aliases"] = item.get("aliases") or ["Madison Ryann Ward"]
    item["enabled"] = False
    item["ticketmasterEnabled"] = False
    item["textMatchEnabled"] = False
    item["socialSearchEnabled"] = False
    item["activeStatus"] = "excluded"
    item["monitoringExcluded"] = True
    item["exclusionReason"] = "Excluded from active Kingdom Circuit tracking 2026-09-11"
    item["rosterOrder"] = roster_order
    return item


def restore_exclusion_tombstone(before: list[dict]) -> None:
    template = next((item for item in before if norm(item.get("name")) == BLOCKED), None)
    roster_order = int((template or {}).get("rosterOrder") or FALLBACK_ROSTER_ORDER)
    original_orders = {
        norm(item.get("name")): int(item.get("rosterOrder") or 0)
        for item in before
        if isinstance(item, dict) and item.get("name") and item.get("rosterOrder")
    }

    artists = [item for item in load_artists() if norm(item.get("name")) != BLOCKED]
    for item in artists:
        original = original_orders.get(norm(item.get("name")))
        if original:
            item["rosterOrder"] = original
        elif int(item.get("rosterOrder") or 0) >= roster_order:
            item["rosterOrder"] = int(item.get("rosterOrder") or 0) + 1

    artists.append(excluded_tombstone(template, roster_order))
    artists.sort(key=lambda item: (int(item.get("rosterOrder") or 99999), norm(item.get("name"))))
    save_artists(artists)


def repair_verified_event_images() -> None:
    """Use source-owned imagery or event-specific branded cards when no official art is available."""
    for path in (audit.EVENTS_FILE, audit.SUPPLEMENTAL_FILE, audit.MANUAL_FILE):
        events = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for event in events:
            event_id = str(event.get("id") or "")
            canonical_id = event_id.removeprefix("manual:")
            override = VERIFIED_EVENT_IMAGES.get(canonical_id)
            if not override:
                continue
            image, image_type = override
            event["image"] = image
            event["imageType"] = image_type
            event["imagePosition"] = "center"
            event["imageOverride"] = True
            changed = True
        if changed:
            path.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify_exclusion() -> None:
    artists = load_artists()
    matches = [item for item in artists if norm(item.get("name")) == BLOCKED]
    if len(matches) != 1:
        raise SystemExit(f"Expected one Madison exclusion tombstone, found {len(matches)}")
    item = matches[0]
    if item.get("enabled") or item.get("ticketmasterEnabled") or item.get("textMatchEnabled") or item.get("socialSearchEnabled"):
        raise SystemExit("Madison Ryann Ward is still enabled for automated tracking")
    if not item.get("monitoringExcluded") or item.get("activeStatus") != "excluded":
        raise SystemExit("Madison Ryann Ward exclusion metadata is incomplete")

    for path in (audit.EVENTS_FILE, audit.SUPPLEMENTAL_FILE, audit.MANUAL_FILE):
        events = json.loads(path.read_text(encoding="utf-8"))
        for event in events:
            if any(norm(artist) == BLOCKED for artist in event.get("artists", [])):
                raise SystemExit(f"Madison remains associated with event {event.get('id')} in {path.name}")
            if norm(event.get("headliner")) == BLOCKED:
                raise SystemExit(f"Madison remains event headliner {event.get('id')} in {path.name}")


def main() -> int:
    before = load_artists()
    result = audit.apply()
    audit.check()
    restore_exclusion_tombstone(before)
    repair_verified_event_images()
    verify_exclusion()
    result["madisonActiveTracking"] = False
    result["madisonTombstonePreserved"] = True
    print(json.dumps(result, indent=2))
    print("September 11 catalog audit enforced with stable roster ordering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
