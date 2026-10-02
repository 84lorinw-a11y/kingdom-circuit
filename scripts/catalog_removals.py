"""Owner-requested complete removals, including archived and refreshed shows."""
import json
import re
from pathlib import Path

# September 28: the owner removed Jay Kalyl from the curated database and
# explicitly requested removal of his profile and every show from the site.
# October 2: remove Propaganda's artist entry and performances, including
# archived/collector records. Host-only billing at another artist's event is
# not a separately confirmed performance by the removed artist.
REMOVED_ARTISTS = {"jay kalyl", "propaganda"}


def removed_artist(name):
    return re.sub(r"[\s_-]+", " ", str(name or "").casefold()).strip() in REMOVED_ARTISTS


def removed_event(event):
    names = [event.get("headliner"), *event.get("artists", []),
             *event.get("advertisedBilling", []), *event.get("officialBill", [])]
    if any(removed_artist(name) for name in names):
        return True
    # Retain the removal even if a stale feed omits the artist association.
    return bool(re.search(r"\b(?:jay[\s_-]*kalyl|propaganda)\b", " ".join(
        str(event.get(key) or "") for key in ("id", "title")), re.I))


def apply(root: Path):
    for relative in ("events.json", "supplemental-events.json", "config/manual-events.json", "event-history.json"):
        path = root / relative
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        rows = data.get("events", []) if isinstance(data, dict) else data
        kept = [entry for entry in rows if not removed_event(entry.get("event", entry))]
        if len(kept) == len(rows):
            continue
        if isinstance(data, dict):
            data["events"] = kept
        else:
            data = kept
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    apply(Path(__file__).resolve().parents[1])
