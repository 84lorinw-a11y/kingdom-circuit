"""Preserve the October 2 artist intake's individually verified concerts."""
from __future__ import annotations

import copy
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def key(event):
    return str(event.get("id") or "").removeprefix("manual:")


def apply(root: Path = ROOT, today: str | None = None):
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    wanted = json.loads((root / "config/oct2-verified-shows.json").read_text())
    paths = ("events.json", "supplemental-events.json", "config/manual-events.json")
    feeds = {name: json.loads((root / name).read_text()) for name in paths}
    history_path = root / "event-history.json"
    history = json.loads(history_path.read_text())
    historical = [entry.get("event", entry) for entry in history.get("events", [])]
    for approved in wanted:
        event_id = approved["id"]
        previous = [row for rows in feeds.values() for row in rows if key(row) == event_id]
        previous += [row for row in historical if key(row) == event_id]
        canonical = copy.deepcopy(approved)
        canonical["id"] = "manual:" + event_id
        canonical["firstSeen"] = min([approved["firstSeen"]] + [row["firstSeen"] for row in previous if row.get("firstSeen")])
        for name, rows in feeds.items():
            rows[:] = [row for row in rows if key(row) != event_id]
            if name == "config/manual-events.json":
                rows.append(dict(copy.deepcopy(canonical), id=event_id))
            elif name == "events.json" and (canonical.get("endDate") or canonical["startDate"]) >= today:
                rows.append(copy.deepcopy(canonical))
        for row in historical:
            if key(row) == event_id:
                row.update(copy.deepcopy(canonical))
    for name, rows in feeds.items():
        (root / name).write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    apply()
    print("October 2 verified concerts restored with complete billing and saved flyers")
