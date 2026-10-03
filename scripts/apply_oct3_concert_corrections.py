"""Restore reviewed October 3 concerts and reject a known artist-name collision."""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
WRONG_NEHEMIAH_IDS = {
    "bandsintown:1039415097", "bandsintown:1039685355", "bandsintown:108952483",
    "bandsintown:108952489", "bandsintown:1040377145", "bandsintown:108952495",
    "bandsintown:108952501",
}
ADRENALINE_DUPLICATE = "bandsintown:1040469553"


def key(event):
    return str(event.get("id") or "").removeprefix("manual:")


def rejected(event):
    if key(event) in WRONG_NEHEMIAH_IDS | {ADRENALINE_DUPLICATE}:
        return True
    # Keep independently verified CHH shows. Only this provider's known metal
    # band identity is rejected, never all events matching the name Nehemiah.
    return str(event.get("bandsintownArtistId") or "") == "15347266"


def apply(root=ROOT, today=None):
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    names = ("events.json", "supplemental-events.json", "config/manual-events.json", "event-history.json")
    data = {name: json.loads((root / name).read_text()) for name in names}
    rows = {name: value.get("events", []) if isinstance(value, dict) else value for name, value in data.items()}
    approved = json.loads((root / "config/oct3-verified-concerts.json").read_text())
    # Retain earliest real discovery across reimports; artwork edits are not new shows.
    for wanted in approved:
        previous = [entry.get("event", entry) for values in rows.values() for entry in values
                    if key(entry.get("event", entry)) == wanted["id"]]
        canonical = copy.deepcopy(wanted)
        canonical["firstSeen"] = min([wanted["firstSeen"]] + [e["firstSeen"] for e in previous if e.get("firstSeen")])
        # A later source-supported cancellation must not be overwritten by this seed.
        changed_status = next((e for e in previous if e.get("status") in {"cancelled", "canceled", "postponed"}), None)
        if changed_status:
            canonical.update({k: copy.deepcopy(v) for k, v in changed_status.items() if k in {"status", "statusNotes", "cancellationReason"}})
        for name, values in rows.items():
            if name == "event-history.json":
                for entry in values:
                    event = entry.get("event", entry)
                    if key(event) == wanted["id"]:
                        event.update(copy.deepcopy(canonical), id="manual:" + wanted["id"])
                continue
            values[:] = [e for e in values if key(e) != wanted["id"]]
            if name == "config/manual-events.json":
                values.append(copy.deepcopy(canonical))
            elif name == "events.json" and (canonical.get("endDate") or canonical["startDate"]) >= today:
                values.append(dict(copy.deepcopy(canonical), id="manual:" + wanted["id"]))
    for name, values in rows.items():
        values[:] = [entry for entry in values if not rejected(entry.get("event", entry))]
        (root / name).write_text(json.dumps(data[name], indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    apply()
    print("October 3 concerts preserved; unrelated Nehemiah band and Adrenaline duplicate removed")
