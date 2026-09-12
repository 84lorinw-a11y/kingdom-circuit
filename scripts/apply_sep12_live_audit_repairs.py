#!/usr/bin/env python3
"""Durable, source-backed repairs confirmed by the September 12, 2026 audit."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVENT_FILES = (
    ROOT / "events.json",
    ROOT / "supplemental-events.json",
    ROOT / "config" / "manual-events.json",
)
RARE_EVENTBRITE_ID = "1986268845586"
RARE_CANCEL_URL = "https://www.eventbrite.com/e/cancelled-rare-of-breed-tickets-1986268845586"
FAITH_JAM_ID = "official:95cc80c13713dfecaf6d"
FAITH_JAM_URL = "https://www.eventbrite.com/e/faith-jam-2026-tickets-1985341605185"


def load(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise SystemExit(f"Expected an event array in {path}")
    return value


def save(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_source(event: dict, source: dict) -> None:
    sources = event.setdefault("sources", [])
    if not any(isinstance(item, dict) and item.get("url") == source["url"] for item in sources):
        sources.append(source)


def apply() -> dict[str, int]:
    report = {"cancelledRecords": 0, "faithJamRecords": 0}
    cancellation_source = {
        "name": "Official Eventbrite cancellation notice",
        "url": RARE_CANCEL_URL,
        "type": "eventbrite",
        "authority": "venue_ticket",
        "priority": 120,
    }
    faith_source = {
        "name": "Official Faith Jam Eventbrite poster",
        "url": FAITH_JAM_URL,
        "type": "eventbrite",
        "authority": "official_event",
        "priority": 112,
    }

    for path in EVENT_FILES:
        rows = load(path)
        changed = False
        for event in rows:
            urls = " ".join(str(event.get(key) or "") for key in ("officialUrl", "ticketUrl"))
            if RARE_EVENTBRITE_ID in urls:
                event["status"] = "cancelled"
                event["cancellationConfirmed"] = True
                event["cancellationConfirmedAt"] = "2026-09-12"
                event["officialUrl"] = RARE_CANCEL_URL
                event["ticketUrl"] = RARE_CANCEL_URL
                event["sourceName"] = "Official Eventbrite cancellation notice"
                event["notes"] = "Cancelled by the organizer. This page is retained as a cancellation notice."
                append_source(event, cancellation_source)
                report["cancelledRecords"] += 1
                changed = True

            if event.get("id") == FAITH_JAM_ID:
                artists = event.setdefault("artists", [])
                if "Brother Bo" not in artists:
                    artists.append("Brother Bo")
                event["venue"] = "White County Fairgrounds"
                event["address"] = "565 Hale Street"
                append_source(event, faith_source)
                event["auditVerified"] = "2026-09-12"
                report["faithJamRecords"] += 1
                changed = True

        if changed:
            save(path, rows)
    return report


def check() -> None:
    for path in EVENT_FILES:
        rows = load(path)
        rare = [event for event in rows if RARE_EVENTBRITE_ID in json.dumps(event)]
        if len(rare) != 1 or rare[0].get("status") != "cancelled" or not rare[0].get("cancellationConfirmed"):
            raise SystemExit(f"Rare of Breed cancellation is not durable in {path}")
        faith = [event for event in rows if event.get("id") == FAITH_JAM_ID]
        if faith:
            event = faith[0]
            if "Brother Bo" not in event.get("artists", []):
                raise SystemExit(f"Brother Bo is missing from Faith Jam in {path}")
            if event.get("venue") != "White County Fairgrounds" or event.get("address") != "565 Hale Street":
                raise SystemExit(f"Faith Jam venue fields are incorrect in {path}")


def main() -> int:
    print(json.dumps(apply(), indent=2))
    check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
