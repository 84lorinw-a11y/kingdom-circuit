"""Keep the owner's reviewed Sheet roster authoritative across refreshes.

The snapshot is deliberately checked in after an owner-requested import. This
module never fetches the Sheet or changes its verification statuses.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def norm(value):
    return str(value or "").strip().casefold()


def snapshot():
    data = json.loads((ROOT / "config/owner-reviewed-roster.json").read_text())
    rows = data["artists"]
    keys = [norm(row["name"]) for row in rows]
    if not keys or "" in keys or len(keys) != len(set(keys)):
        raise ValueError("Owner roster snapshot contains missing or duplicate names")
    return rows


def approved(name):
    return norm(name) in {norm(row["name"]) for row in snapshot()}


def removed_names():
    data = json.loads((ROOT / "config/owner-reviewed-roster.json").read_text())
    return data.get("removedArtists", [])


def filter_events(records):
    """Remove deleted-only listings; preserve mixed bills and historical records."""
    removed = {norm(name) for name in removed_names()}
    kept = []
    for row in records:
        names = {norm(n) for n in [*(row.get("artists") or []),
                                  row.get("headliner"), row.get("trackedArtist")] if n}
        if names and names.issubset(removed):
            continue
        kept.append(row)
    return kept


def order_records(records):
    positions = {norm(row["name"]): i for i, row in enumerate(snapshot(), 1)}
    kept = [row for row in records if norm(row.get("name")) in positions]
    kept.sort(key=lambda row: positions[norm(row["name"])])
    for i, row in enumerate(kept, 1):
        row["rosterOrder"] = i
    return kept


def verify_records(records):
    actual = [norm(row["name"]) for row in records]
    expected = [norm(row["name"]) for row in snapshot()]
    if actual != expected:
        raise ValueError("Artist database no longer matches the owner-reviewed roster")


def filter_source_records(records):
    """Stop dedicated calendars for removed artists without losing shared feeds."""
    allowed = {norm(row["name"]) for row in snapshot()}
    result = []
    for row in records:
        names = [row.get("artist"), *(row.get("artists") or [])]
        names = [name for name in names if name]
        if names and not any(norm(name) in allowed for name in names):
            continue
        result.append(row)
    return result


def apply(root=ROOT):
    path = root / "config/artists.json"
    rows = order_records(json.loads(path.read_text()))
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    for relative in ("config/official-sources.json",):
        path = root / relative
        if path.exists():
            records = filter_source_records(json.loads(path.read_text()))
            path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    for relative in ("events.json", "supplemental-events.json", "config/manual-events.json"):
        path = root / relative
        if path.exists():
            records = filter_events(json.loads(path.read_text()))
            path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    return rows
