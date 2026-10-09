"""Keep owner-approved discoveries durable across provider refreshes."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

BATCH = "2026-09-29-expanded-source-search"
APPROVED_BATCHES = {BATCH, "2026-09-30-whatuprg-announced", "2026-10-05-submitted-shows", "2026-10-06-submitted-events", "2026-10-07-submitted-events", "2026-10-07-reviewed-discoveries", "2026-10-08-reviewed-discoveries"}


def matches(event, approved):
    identifier = str(event.get("id", "")).removeprefix("manual:")
    if identifier == approved["id"]:
        return True
    if event.get("startDate") != approved["startDate"]:
        return False
    if str(event.get("id", "")) in approved.get("sourceEventIds", []):
        return True
    if approved.get("bandsintownEventId") and str(event.get("bandsintownEventId", "")) == str(approved["bandsintownEventId"]):
        return True
    urls = {str(approved.get(k, "")).split("?")[0].rstrip("/")
            for k in ("officialUrl", "ticketUrl")} - {""}
    return any(str(event.get(k, "")).split("?")[0].rstrip("/") in urls
               for k in ("officialUrl", "ticketUrl"))


def apply(root: Path, events: list, supplemental: list, today=None):
    # The owner released the Alex Jean Dallas hold on October 8 after the
    # venue corroborated the AXS listing. Its approved record now dedupes here.
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
