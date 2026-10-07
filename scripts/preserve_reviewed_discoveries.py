"""Keep owner-approved discoveries and a specific unresolved Dallas hold durable."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

BATCH = "2026-09-29-expanded-source-search"
APPROVED_BATCHES = {BATCH, "2026-09-30-whatuprg-announced", "2026-10-05-submitted-shows", "2026-10-06-submitted-events", "2026-10-07-submitted-events"}


def held_dallas_candidate(event):
    if str(event.get("startDate", ""))[:10] != "2026-11-19":
        return False
    urls = " ".join(str(event.get(k, "")) for k in ("officialUrl", "ticketUrl"))
    names = {str(n).casefold() for n in event.get("artists", [])}
    return "1626463" in urls or (
        "alex jean" in names and str(event.get("city", "")).casefold() == "dallas"
    )


def matches(event, approved):
    identifier = str(event.get("id", "")).removeprefix("manual:")
    if identifier == approved["id"]:
        return True
    if event.get("startDate") != approved["startDate"]:
        return False
    urls = {str(approved.get(k, "")).split("?")[0].rstrip("/")
            for k in ("officialUrl", "ticketUrl")} - {""}
    return any(str(event.get(k, "")).split("?")[0].rstrip("/") in urls
               for k in ("officialUrl", "ticketUrl"))


def apply(root: Path, events: list, supplemental: list, today=None):
    # Dallas is explicitly held by the owner pending an accessible official
    # ticket listing and venue corroboration. Do not let a collector publish it.
    events[:] = [e for e in events if not held_dallas_candidate(e)]
    supplemental[:] = [e for e in supplemental if not held_dallas_candidate(e)]
    path = root / "config/manual-events.json"
    if not path.exists():
        return
    today = today or datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    for approved in json.loads(path.read_text()):
        if approved.get("editorialBatch") not in APPROVED_BATCHES:
            continue
        if str(approved.get("endDate") or approved["startDate"]) < today:
            continue
        existing = [e for e in events + supplemental if matches(e, approved)]
        # Never turn newer cancellation/postponement evidence back into a show.
        if any(e.get("status") in {"cancelled", "canceled", "postponed"}
               for e in existing + [approved]):
            continue
        restored = deepcopy(approved)
        restored["id"] = "manual:" + approved["id"]
        ages = [e["firstSeen"] for e in existing + [approved] if e.get("firstSeen")]
        if ages:
            restored["firstSeen"] = min(ages)
        events[:] = [e for e in events if not matches(e, approved)]
        supplemental[:] = [e for e in supplemental if not matches(e, approved)]
        events.append(restored)
