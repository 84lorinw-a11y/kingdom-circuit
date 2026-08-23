#!/usr/bin/env python3
"""Run Bandsintown refresh without self-deduping previously published BIT rows.

The underlying collector correctly dedupes Bandsintown against the main catalog and
non-Bandsintown supplemental events. Previously, however, it also compared fresh
Bandsintown rows against its own prior output, then replaced those prior rows with
an empty result. This wrapper removes prior Bandsintown-generated rows only for the
comparison phase, runs the collector, and preserves prior rows for artists whose
Bandsintown request explicitly failed during this run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPLEMENTAL = ROOT / "supplemental-events.json"
STATUS = ROOT / "bandsintown-status.json"


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def norm(value) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def is_bit(event) -> bool:
    return isinstance(event, dict) and str(event.get("id") or "").startswith("bandsintown:")


def main() -> int:
    original = load(SUPPLEMENTAL, [])
    if not isinstance(original, list):
        raise SystemExit("supplemental-events.json must be an array")

    prior_bit = [event for event in original if is_bit(event)]
    non_bit = [event for event in original if not is_bit(event)]

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

    fresh_bit = [event for event in refreshed if is_bit(event)]
    fresh_non_bit = [event for event in refreshed if not is_bit(event)]

    # If a specific artist's request failed, keep that artist's last known rows for
    # this run rather than deleting valid shows because of a transient API problem.
    failed_artists = {
        norm(item.get("artist"))
        for item in status.get("errors", [])
        if isinstance(item, dict) and item.get("artist")
    }
    fresh_ids = {str(event.get("id") or "") for event in fresh_bit}
    preserved = [
        event for event in prior_bit
        if norm(event.get("trackedArtist") or event.get("headliner")) in failed_artists
        and str(event.get("id") or "") not in fresh_ids
    ]

    merged = [*fresh_non_bit, *fresh_bit, *preserved]
    merged.sort(key=lambda event: (str(event.get("startDate") or "9999-12-31"), str(event.get("title") or "")))
    save(SUPPLEMENTAL, merged)

    status["activeNonFestivalBandsintownShows"] = len(fresh_bit) + len(preserved)
    status["priorBandsintownShows"] = len(prior_bit)
    status["preservedDueToRequestErrors"] = len(preserved)
    save(STATUS, status)

    print(
        "Bandsintown refresh safeguard: "
        f"prior={len(prior_bit)}, fresh={len(fresh_bit)}, preserved_on_error={len(preserved)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
