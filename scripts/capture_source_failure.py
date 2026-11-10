#!/usr/bin/env python3
"""Save limited public concert facts for a failed source-preparation review.

This is diagnostic evidence, never a publication input. No raw status reports,
URLs, configuration, environment values, caches or error strings are copied.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from apply_curated_catalog_policy import is_known_duplicate_fragment
from catalog_removals import removed_event
from private_events import matches as private_match
from run_bandsintown_refresh import exact_identities
from show_information_model import is_private_event

ROOT = Path(__file__).resolve().parents[1]
FEEDS = ("events.json", "supplemental-events.json", "artist-website-events.json")
FIELDS = ("id", "title", "startDate", "startTime", "timezone", "venue", "city",
          "state", "country", "artists", "status", "doorsTime")
UNSAFE_TEXT = re.compile(r"(?:[a-z][a-z0-9+.-]*://|www\.|mailto:|"
    r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|authorization|password)\s*[:=])", re.I)


def read_rows(path):
    if path.is_symlink():
        raise ValueError("Symlink input is not an allowed diagnostic source")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError("Expected a list of records")
    return value


def excluded(event, private, held):
    if (is_private_event(event) or event.get("holdReason") or event.get("publish") is False
            or str(event.get("status") or "").casefold() in {"held", "hold", "removed"}
            or removed_event(event) or is_known_duplicate_fragment(event)):
        return True
    identities = exact_identities(event)
    if any(private_match(event, record) or identities & exact_identities(record) for record in private):
        return True
    for record in held:
        if record.get("publish") is False:
            rejected = exact_identities(record.get("event") or {})
            if record.get("excludedEventId"):
                rejected.add(record["excludedEventId"])
            if identities & rejected:
                return True
    return False


def public_fields(event):
    result = {}
    for field in FIELDS:
        value = event.get(field)
        if field == "artists":
            if isinstance(value, list):
                result[field] = [name for name in value if isinstance(name, str)
                                 and len(name) <= 1000 and not UNSAFE_TEXT.search(name)]
        elif isinstance(value, str) and len(value) <= 1000 and not UNSAFE_TEXT.search(value):
            result[field] = value
    return result


def snapshot(source):
    report = {"schemaVersion": 1, "capturedAt": datetime.now(timezone.utc).isoformat(),
              "purpose": "failed_source_diagnostic_not_publication_input", "inputs": {}}
    try:
        # These existing policies are consulted only for exclusions, never copied.
        private = read_rows(source / "config/private-events.json")
        held = read_rows(source / "config/review-held-events.json")
    except (OSError, ValueError, TypeError):
        report["policyStatus"] = "unavailable"
        return report  # Without privacy/hold proof, capture no concert records.
    report["policyStatus"] = "ok"
    for name in FEEDS:
        try:
            events = read_rows(source / name)
        except FileNotFoundError:
            report["inputs"][name] = {"status": "missing"}
            continue
        except (OSError, ValueError, TypeError):
            report["inputs"][name] = {"status": "unreadable"}
            continue
        captured = []
        for event in events:
            try:
                if not excluded(event, private, held):
                    captured.append(public_fields(event))
            except (KeyError, TypeError, ValueError, AttributeError):
                continue  # Malformed identity/privacy data must not reveal a row.
        report["inputs"][name] = {"status": "ok", "inputCount": len(events),
                                  "omittedCount": len(events) - len(captured), "events": captured}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.source.resolve()):
        parser.error("Diagnostic output must be outside the source checkout")
    report = snapshot(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Limited source-failure diagnostic saved")


if __name__ == "__main__":
    main()
