#!/usr/bin/env python3
"""Maintain a durable history of every show ever observed on the calendar.

The public events.json can remain future-focused while event-history.json keeps
historical data for year-end recaps, artist show counts, geography, festivals,
and other analysis. Each run also backfills every recoverable historical version
of events.json from git so older calendar entries are not lost.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
EVENTS_FILE = ROOT / "events.json"
HISTORY_FILE = ROOT / "event-history.json"
HISTORY_VERSION = 2


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def git_event_snapshots() -> list[tuple[str, list[dict[str, Any]]]]:
    """Return recoverable events.json snapshots in chronological commit order."""
    try:
        log = subprocess.run(
            ["git", "log", "--format=%H%x09%cI", "--", "events.json"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []

    commits: list[tuple[str, str]] = []
    for line in log.splitlines():
        if "\t" not in line:
            continue
        sha, committed_at = line.split("\t", 1)
        commits.append((sha.strip(), committed_at.strip()))

    snapshots: list[tuple[str, list[dict[str, Any]]]] = []
    for sha, committed_at in reversed(commits):
        try:
            raw = subprocess.run(
                ["git", "show", f"{sha}:events.json"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            parsed = json.loads(raw)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        if not isinstance(parsed, list):
            continue
        events = [event for event in parsed if isinstance(event, dict)]
        snapshots.append((committed_at, events))
    return snapshots


def earlier_iso(current: str, candidate: str) -> str:
    current_dt = parse_iso_datetime(current)
    candidate_dt = parse_iso_datetime(candidate)
    if candidate_dt is None:
        return current
    if current_dt is None or candidate_dt < current_dt:
        return candidate
    return current


def later_iso(current: str, candidate: str) -> str:
    current_dt = parse_iso_datetime(current)
    candidate_dt = parse_iso_datetime(candidate)
    if candidate_dt is None:
        return current
    if current_dt is None or candidate_dt > current_dt:
        return candidate
    return current


def upsert_snapshot(
    events: Iterable[dict[str, Any]],
    observed_at: str,
    by_key: dict[str, dict[str, Any]],
    records: list[dict[str, Any]],
    today: date,
    *,
    from_git: bool,
) -> int:
    added = 0
    observed_dt = parse_iso_datetime(observed_at)
    observed_date = observed_dt.date() if observed_dt else today

    for raw_event in events:
        event = dict(raw_event)
        key = archive_key(event)
        record = by_key.get(key)
        if record is None:
            record = {
                "archiveKey": key,
                "firstArchivedAt": now_iso(),
                "firstSeenOnCalendar": event.get("firstSeen") or observed_at,
                "lastSeenOnCalendar": observed_at,
                "calendarPresence": "absent",
                "removedFromCalendarAt": "",
                "reappearedCount": 0,
                "observedOnOrAfterEventDate": False,
                "firstObservedOnOrAfterEventDate": "",
                "dateState": date_state(event, today),
                "observedInGitHistory": False,
                "firstGitObservedAt": "",
                "lastGitObservedAt": "",
                "event": event,
            }
            records.append(record)
            by_key[key] = record
            added += 1
        else:
            record["firstSeenOnCalendar"] = earlier_iso(
                str(record.get("firstSeenOnCalendar") or ""),
                str(event.get("firstSeen") or observed_at),
            )
            record["lastSeenOnCalendar"] = later_iso(
                str(record.get("lastSeenOnCalendar") or ""), observed_at
            )

        previous_last = parse_iso_datetime(str(record.get("lastSeenOnCalendar") or ""))
        if previous_last is None or observed_dt is None or observed_dt >= previous_last:
            record["event"] = event

        if from_git:
            record["observedInGitHistory"] = True
            record["firstGitObservedAt"] = earlier_iso(
                str(record.get("firstGitObservedAt") or ""), observed_at
            )
            record["lastGitObservedAt"] = later_iso(
                str(record.get("lastGitObservedAt") or ""), observed_at
            )

        event_date = parse_event_date(event)
        if event_date is not None and event_date <= observed_date:
            current_first = str(record.get("firstObservedOnOrAfterEventDate") or "")
            record["firstObservedOnOrAfterEventDate"] = earlier_iso(current_first, observed_at)
            record["observedOnOrAfterEventDate"] = True

        record["dateState"] = date_state(record.get("event") or event, today)

    return added


def main() -> None:
    current = load_json(EVENTS_FILE, [])
    if not isinstance(current, list):
        raise SystemExit("events.json must contain a JSON array")
    current_events = [event for event in current if isinstance(event, dict)]

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

    snapshots = git_event_snapshots()
    historical_added = 0
    for observed_at, snapshot_events in snapshots:
        historical_added += upsert_snapshot(
            snapshot_events,
            observed_at,
            by_key,
            records,
            today,
            from_git=True,
        )

    current_keys = {archive_key(event) for event in current_events}
    previously_absent = {
        key for key, record in by_key.items() if record.get("calendarPresence") == "absent"
    }
    current_added = upsert_snapshot(
        current_events,
        timestamp,
        by_key,
        records,
        today,
        from_git=False,
    )

    reappeared = 0
    removed = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        key = str(record.get("archiveKey") or "")
        event = record.get("event") if isinstance(record.get("event"), dict) else {}
        record["dateState"] = date_state(event, today)
        if key in current_keys:
            if key in previously_absent:
                record["reappearedCount"] = int(record.get("reappearedCount") or 0) + 1
                reappeared += 1
            record["calendarPresence"] = "present"
            record["removedFromCalendarAt"] = ""
            record["lastSeenOnCalendar"] = later_iso(
                str(record.get("lastSeenOnCalendar") or ""), timestamp
            )
        else:
            if record.get("calendarPresence") == "present":
                removed += 1
            record["calendarPresence"] = "absent"
            if not record.get("removedFromCalendarAt"):
                record["removedFromCalendarAt"] = timestamp

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
        "pastDated": sum(1 for record in records if record.get("dateState") == "past"),
        "observedOnOrAfterEventDate": sum(1 for record in records if record.get("observedOnOrAfterEventDate")),
        "gitSnapshotsScanned": len(snapshots),
        "gitHistoryBackfilled": sum(1 for record in records if record.get("observedInGitHistory")),
    }
    write_json(HISTORY_FILE, history)
    print(
        f"Event history updated: {len(records)} total; {len(snapshots)} git snapshots; "
        f"{historical_added} historical additions; {current_added} current additions; "
        f"{removed} removed; {reappeared} reappeared."
    )


if __name__ == "__main__":
    main()
