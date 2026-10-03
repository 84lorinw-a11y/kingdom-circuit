#!/usr/bin/env python3
"""Run the exhaustive discovery pass with structured Bandsintown first.

Public Bandsintown HTML is blocked from GitHub-hosted runners. The repository
already has a conservative REST collector with identity checks, duplicate
filtering, festival holds, and preservation on transient request errors. This
orchestrator makes that collector the Bandsintown path for full scans, then runs
the remaining Songkick/official-site/Spotify discovery surfaces without wasting
hundreds of blocked HTML requests.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_bandsintown_refresh  # type: ignore
import scan_all_artist_sources_legacy as expanded  # type: ignore

FULL_STATUS = ROOT / "full-scan-status.json"
BIT_STATUS = ROOT / "bandsintown-status.json"
BIT_CANDIDATES = ROOT / "bandsintown-candidates.json"
FULL_CANDIDATES = ROOT / "full-scan-candidates.json"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def delegated_bandsintown(artist, _client, _alias_lookup, _checked_at):
    name = str(artist.get("name") or "").strip()
    return [], {
        "artist": name,
        "source": "Bandsintown",
        "status": "delegated_to_structured_rest",
        "eventsFound": 0,
    }


def candidate_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("title") or "").strip().casefold(),
        str(item.get("startDate") or "")[:10],
        str(item.get("city") or "").strip().casefold(),
        str(item.get("venue") or "").strip().casefold(),
    )


def merge_candidates() -> int:
    full = load_json(FULL_CANDIDATES, [])
    bit = load_json(BIT_CANDIDATES, [])
    if not isinstance(full, list):
        full = []
    if not isinstance(bit, list):
        bit = []
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for raw in [*full, *bit]:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        if raw in bit and not item.get("reason"):
            item["reason"] = str(item.get("holdReason") or "festival_needs_official_lineup_confirmation")
        key = candidate_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    save_json(FULL_CANDIDATES, merged)
    return len(merged)


def merge_bandsintown_status(full_status: dict[str, Any], bit_status: dict[str, Any], error: str = "") -> dict[str, Any]:
    checked = int(bit_status.get("artistsChecked") or full_status.get("artistsChecked") or 0)
    resolved = int(bit_status.get("artistsResolved") or 0)
    raw_rows = int(bit_status.get("rawUpcomingUSRows") or 0)
    published = int(bit_status.get("newNonFestivalShowsPublished") or 0)
    held = int(bit_status.get("festivalCandidatesHeld") or 0)
    request_errors = int(bit_status.get("requestErrors") or 0)
    full_status["bandsintown"] = {
        "discoveryMode": "structured_rest",
        "status": "failed_preserved_prior" if error else "ok",
        "artistsAttempted": checked,
        "resolved": resolved,
        "rawUpcomingUSRows": raw_rows,
        "newEventsPublished": published,
        "festivalCandidatesHeld": held,
        "requestErrors": request_errors,
    }
    if error:
        full_status["bandsintown"]["error"] = error[:500]
    full_status["bandsintownHtml"] = {
        "status": "skipped_structured_rest_used",
        "reason": "Public Bandsintown HTML is robot-blocked on GitHub runners; structured REST is authoritative for this pass.",
    }
    return full_status


def main() -> int:
    bit_error = ""
    try:
        result = int(run_bandsintown_refresh.main())
        if result:
            bit_error = f"structured Bandsintown collector returned {result}"
    except Exception as exc:  # safeguard restores prior rows before raising
        bit_error = f"{type(exc).__name__}: {exc}"
        print(f"Structured Bandsintown refresh failed; preserved prior provider rows: {bit_error}", file=sys.stderr)

    # Never retry Bandsintown through the public HTML search surface. Continue
    # the complementary discovery sources even if the structured API had a
    # transient failure; the prior Bandsintown rows have already been restored.
    expanded.collect_bandsintown_for_artist = delegated_bandsintown
    expanded_result = int(expanded.main())
    candidate_count = merge_candidates()

    full_status = load_json(FULL_STATUS, {})
    if not isinstance(full_status, dict):
        full_status = {}
    bit_status = load_json(BIT_STATUS, {})
    if not isinstance(bit_status, dict):
        bit_status = {}
    full_status = merge_bandsintown_status(full_status, bit_status, bit_error)
    full_status["festivalCandidates"] = candidate_count
    save_json(FULL_STATUS, full_status)
    return expanded_result


if __name__ == "__main__":
    raise SystemExit(main())
