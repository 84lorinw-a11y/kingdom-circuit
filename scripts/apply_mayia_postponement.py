"""Preserve the artist-confirmed Songs That Speak postponement after refreshes."""
import json
from pathlib import Path

EVENT_ID = "mayia-songs-that-speak-conference-pleasant-garden-2026"
SOURCE = "https://www.instagram.com/p/Dehg-BzRvR5/"
NOTICE = ("Postponed — new date to be announced. MAYIA and the Songs That Speak "
          "Conference team announced that the October 23–24, 2026 conference at "
          "New Covenant Church in Pleasant Garden, NC has been postponed.")


def patch_event(event):
    # Match the original dates only: a subsequently confirmed new date needs
    # its own review and must not inherit this postponement automatically.
    if event.get("startDate") not in {"2026-10-23", "2026-10-24"}:
        return False
    same_id = str(event.get("id", "")).removeprefix("manual:") == EVENT_ID
    same_conference = ("songs that speak" in str(event.get("title", "")).casefold()
                       and str(event.get("city", "")).casefold() == "pleasant garden")
    if not (same_id or same_conference):
        return False
    event.update(status="postponed", ticketUrl="", officialUrl=SOURCE,
                 publicDescription=NOTICE, auditVerified="2026-10-15",
                 sourceName="MAYIA and Songs That Speak Conference postponement announcement")
    sources = event.setdefault("sources", [])
    if not any(item.get("url") == SOURCE for item in sources):
        sources.insert(0, {"name": event["sourceName"], "url": SOURCE,
                           "type": "manual_verified", "authority": "official_event", "priority": 120})
    note = "October 15 artist/organizer announcement supersedes the original schedule. New date not announced; retain original date as historical context only. " + SOURCE
    if note not in event.get("notes", ""):
        event["notes"] = (event.get("notes", "") + " " + note).strip()
    return True


def apply(root):
    for relative in ("config/manual-events.json", "events.json", "supplemental-events.json", "event-history.json"):
        path = root / relative
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        rows = data.get("events", []) if isinstance(data, dict) else data
        before = json.dumps(data, ensure_ascii=False)
        for row in rows:
            patch_event(row.get("event", row))
        if json.dumps(data, ensure_ascii=False) != before:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    apply(Path(__file__).resolve().parents[1])
