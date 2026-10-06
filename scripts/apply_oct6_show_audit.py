"""Preserve owner-approved October 6 accuracy corrections across refreshes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLO_ID = "bandsintown:1040378722"
OLD_GLO_ID = "cj-emulous-glo-concert-los-angeles-2026"
OLD_GLO_URLS = {
    "https://www.cjemulous.com/event-details/gloconcert",
    "https://www.cjemulous.com/event-details/glovember-1",
}
OLD_GLO_PATH = "/event/glo-concert-2026-11-15-los-angeles-1f2b48/"
GLO_NOTICE = "GLOVEMBER takes place November 14, 2026 at 8 PM at The Belasco. This duplicate listing has been combined with the main event."
RUSLAN = {
    "bandsintown:108144023": ("2026-10-24", "3A00636DD48C7831", "The Bronze Peacock at House of Blues Houston", "1204 Caroline St"),
    "bandsintown:108144061": ("2026-10-25", "0C00636EDD9DABAC", "The Echo Lounge & Music Hall", "1323 N Stemmons Fwy"),
}


def key(event):
    return str(event.get("id") or "").removeprefix("manual:")


def urls(event):
    return {str(event.get(field) or "").split("?")[0].rstrip("/")
            for field in ("officialUrl", "ticketUrl")}


def old_glo(event):
    return (event.get("startDate") in {"2026-11-14", "2026-11-15"}
            and (key(event) == OLD_GLO_ID or bool(urls(event) & OLD_GLO_URLS)))


def patch_event(event):
    """Exact-event/date patches; never overwrite a later cancellation or move."""
    identity = key(event)
    for event_id, (date, ticket_id, venue, address) in RUSLAN.items():
        if event.get("startDate") == date and (identity == event_id or any(
                f"/event/{ticket_id}" in url for url in urls(event))):
            event.update(venue=venue, address=address, timezone="America/Chicago",
                         auditVerified="2026-10-06")
    if old_glo(event):
        event.update(status="merged", mergedIntoId=GLO_ID, auditVerified="2026-10-06",
                     mergeReason=GLO_NOTICE,
                     notes="October 6 source review: CJ's GLOvember page links the same Ticketmaster event 09006537CF500ECC as the November 14 Belasco show. Retain this old identity only as a redirect, not a November 15 performance.")
    elif identity == GLO_ID and event.get("startDate") == "2026-11-14":
        event["legacyEventPaths"] = list(dict.fromkeys([
            *event.get("legacyEventPaths", []), OLD_GLO_PATH]))
        event["legacyEventNotice"] = GLO_NOTICE
        event["mergedFromIds"] = list(dict.fromkeys([
            *event.get("mergedFromIds", []), "manual:" + OLD_GLO_ID]))


def apply(root=ROOT):
    from catalog_removals import withheld_event

    names = ("events.json", "supplemental-events.json", "config/manual-events.json", "event-history.json")
    data = {name: json.loads((root / name).read_text()) for name in names if (root / name).exists()}
    entries = [entry for value in data.values()
               for entry in (value.get("events", []) if isinstance(value, dict) else value)]
    rows = [entry.get("event", entry) for entry in entries]
    # Merging old links must not make GLOVEMBER appear newly discovered.
    first_seen = [str(entry.get("firstSeen") or row.get("firstSeen"))
                  for entry, row in zip(entries, rows)
                  if (key(row) == GLO_ID or old_glo(row))
                  and (entry.get("firstSeen") or row.get("firstSeen"))]
    for row in rows:
        patch_event(row)
        if key(row) == GLO_ID and row.get("startDate") == "2026-11-14" and first_seen:
            row["firstSeen"] = min(first_seen)
    for name, value in data.items():
        values = value.get("events", []) if isinstance(value, dict) else value
        values[:] = [entry for entry in values if not withheld_event(entry.get("event", entry))]
        (root / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    apply()
    print("October 6 show accuracy corrections preserved")
