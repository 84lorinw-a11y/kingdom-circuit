"""Preserve owner-requested official show artwork across calendar refreshes.

Pins are scoped to an existing event identity and date. They never create an
event, reset discovery age, change schedules, or expand the curated roster.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = json.loads((ROOT / "config/verified-show-artwork.json").read_text())
BY_ID = {pin["id"]: pin for pin in PINS}


def patch_event(event):
    event_id = str(event.get("id") or "").removeprefix("manual:")
    pin = BY_ID.get(event_id)
    if not pin or event.get("startDate") != pin["startDate"]:
        return False
    event.update(copy.deepcopy({key: value for key, value in pin.items()
                                if key not in {"id", "startDate"}}))
    return True


def apply(root=ROOT):
    for name in ("events.json", "supplemental-events.json", "config/manual-events.json", "event-history.json"):
        path = root / name
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        rows = data.get("events", []) if isinstance(data, dict) else data
        changed = False
        for entry in rows:
            event = entry.get("event", entry)
            before = copy.deepcopy(event)
            patch_event(event)
            changed = changed or before != event
        if changed:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    apply()
