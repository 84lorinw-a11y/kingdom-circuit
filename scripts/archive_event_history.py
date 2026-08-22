#!/usr/bin/env python3
"""Maintain an append-only history of every show observed on the live calendar.

The history is intentionally separate from events.json so the public calendar can
remain future-focused while Kingdom Circuit keeps durable data for year-end
recaps, artist show counts, geography, festivals, and other historical analysis.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
HISTORY_FILE = ROOT / "event-history.json"
HISTORY_VERSION = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def normalize(value: Any) -> str:
    text = str(value or "").casefold().strip()
    return re.sub(r"\s+", " ", text)


def archive_key(event: dict[str, Any]) -> str:
    event_id = normalize(event.get("id"))
    if event_id:
        return f"id:{event_id}"

    artists = event.get("artists") if isinstance(event.get("artists"), list) else []
    signature = "|".join(
        [
            normalize(event.get("startDate")),
            normalize(event.get("startTime")),
            normalize(event.get("title")),
            normalize(event.get("venue")),
            normalize(event.get("city")),
            normalize(event.get("state")),
            normalize(event.get("headliner")),
            ",".join(sorted(normalize(artist) for artist in artists if normalize(artist))),
        ]
    )
    return "sig:" + hashlib.sha1(signature.encode("utf-8")).hexdigest()


def parse_event_date(event: dict[str, Any]) -> date | None:
    raw = str(event.get("startDate") or "").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def date_state(event: dict[str, Any], today: date) -> str:
    event_date = parse_event_date(event)
    if event_date is None:
        return "unknown"
    if event_date < today:
        return "past"
    if event_date == today:
        return "today"
    return "upcoming"


def main() -> None:
    current = load_json(EVENTS_FILE, [])
    if not isinstance(current, list):
        raise SystemExit("events.json must contain a JSON array")

    history = load_json(
        HISTORY_FILE,
        {"historyVersion": HISTORY_VERSION, "updatedAt": "", "events": []},
    )
    if not isinstance(history, dict):
        raise SystemExit("event-history.json must contain a JSON object")
    records = history.get("events", [])
    if not isinstance(records, list):
        raise SystemExit("event-history.json events must be a JSON array")

    timestamp = now_iso()
    today = datetime.now(timezone.utc).date()
    by_key: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        key = str(record.get("archiveKey") or "")
        if key:
            by_key[key] = record

    seen: set[str] = set()
    added = 0
    reappeared = 0

    for raw_event in current:
        if not isinstance(raw_event, dict):
            continue
        event = dict(raw_event)
        key = archive_key(event)
        seen.add(key)
        record = by_key.get(key)
        if record is None:
            record = {
                "archiveKey": key,
                "firstArchivedAt": timestamp,
                "firstSeenOnCalendar": event.get("firstSeen") or timestamp,
                "lastSeenOnCalendar": timestamp,
                "calendarPresence": "present",
                "removedFromCalendarAt": "",
                "reappearedCount": 0,
                "observedOnOrAfterEventDate": False,
                "firstObservedOnOrAfterEventDate": "",
                "dateState": date_state(event, today),
                "event": event,
            }
            records.append(record)
            by_key[key] = record
            added += 1
        else:
            if record.get("calendarPresence") == "absent":
                record["reappearedCount"] = int(record.get("reappearedCount") or 0) + 1
                reappeared += 1
            record["event"] = event
            record["lastSeenOnCalendar"] = timestamp
            record["calendarPresence"] = "present"
            record["removedFromCalendarAt"] = ""
            record["dateState"] = date_state(event, today)

        event_date = parse_event_date(event)
        if event_date is not None and event_date <= today:
            if not record.get("observedOnOrAfterEventDate"):
                record["firstObservedOnOrAfterEventDate"] = timestamp
            record["observedOnOrAfterEventDate"] = True

    removed = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        key = str(record.get("archiveKey") or "")
        event = record.get("event") if isinstance(record.get("event"), dict) else {}
        record["dateState"] = date_state(event, today)
        if key and key not in seen and record.get("calendarPresence") != "absent":
            record["calendarPresence"] = "absent"
            record["removedFromCalendarAt"] = timestamp
            removed += 1

    records.sort(
        key=lambda record: (
            str((record.get("event") or {}).get("startDate") or "9999-12-31"),
            str((record.get("event") or {}).get("startTime") or ""),
            str(record.get("archiveKey") or ""),
        )
    )

    history["historyVersion"] = HISTORY_VERSION
    history["updatedAt"] = timestamp
    history["events"] = records
    history["summary"] = {
        "totalArchived": len(records),
        "currentlyPresent": sum(1 for record in records if record.get("calendarPresence") == "present"),
        "observedOnOrAfterEventDate": sum(1 for record in records if record.get("observedOnOrAfterEventDate")),
    }
    write_json(HISTORY_FILE, history)
    print(
        f"Event history updated: {len(records)} total, {added} added, "
        f"{removed} removed, {reappeared} reappeared."
    )


if __name__ == "__main__":
    main()
