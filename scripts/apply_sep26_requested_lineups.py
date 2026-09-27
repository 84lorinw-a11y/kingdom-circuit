"""Keep the owner's individually reviewed festival and concert corrections."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCHES = json.loads((ROOT / "config/sep26-requested-lineups.json").read_text())


def patch_event(event):
    event_id = str(event.get("id") or "").removeprefix("manual:")
    wanted = PATCHES.get(event_id)
    if not wanted or event.get("startDate") != wanted["startDate"]:
        return False
    sources = event.get("sources", [])
    legacy = event.get("legacyEventPaths", [])
    event.update(copy.deepcopy(wanted))
    event["sources"] = copy.deepcopy(wanted.get("sources", [])) + [
        s for s in sources if s.get("url") not in {x["url"] for x in wanted.get("sources", [])}]
    if wanted.get("legacyEventPaths"):
        event["legacyEventPaths"] = list(dict.fromkeys(wanted["legacyEventPaths"] + legacy))
    return True
