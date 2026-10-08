"""Check reviewed discoveries and the October 6 archive in the final artifact."""
import html
import json
from pathlib import Path
import re
import sys

import build_seo_site as builder
from verify_egr_bizzle_updates import uses_image

ROOT = Path(__file__).resolve().parents[1]
BATCH = "2026-10-07-reviewed-discoveries"


def verify(site):
    rows = builder.merge_events(json.loads((site / "events.json").read_text()),
                                json.loads((site / "supplemental-events.json").read_text()))
    approved = [e for e in json.loads((ROOT / "config/manual-events.json").read_text())
                if e.get("editorialBatch") == BATCH]
    checked = 0
    for wanted in approved:
        if not builder.current(wanted):
            continue
        matches = [e for e in rows if str(e["id"]).removeprefix("manual:") == wanted["id"]]
        assert len(matches) == 1, (wanted["id"], "missing or duplicate")
        event = matches[0]
        for field in ("startDate", "startTime", "venue", "city", "state", "artists", "advertisedBilling", "officialUrl"):
            assert event.get(field) == wanted.get(field), (wanted["id"], field)
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        assert uses_image(detail, site, wanted["image"]), (wanted["id"], "source artwork")
        for name in wanted["advertisedBilling"]:
            assert name in html.unescape(detail), (wanted["id"], name)
        assert href in (site / "shows/index.html").read_text(), (wanted["id"], "shows list")
        checked += 1

    history = json.loads((ROOT / "event-history.json").read_text())["events"]
    for identity in ("bandsintown:1040305060", "manual:after-doves-at-the-cg-nashville-2026-10-06"):
        event = next(row["event"] for row in history if row["event"].get("id") == identity)
        assert not any(e["id"] == identity for e in rows), (identity, "still upcoming")
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        assert re.search(r"past (?:show|event)", detail, re.I), (identity, "missing archive notice")
        for name in event["artists"]:
            profile = site / builder.artist_path(name).strip("/") / "index.html"
            assert href in profile.read_text(), (identity, name, "missing artist archive")
        if "after-doves" in identity:
            # Existing archive pages intentionally display calendar dates only;
            # the durable record must still retain the exact overnight timing.
            assert event["endDate"] == "2026-10-06"
            assert event["endDateTime"] == "2026-10-07T00:00:00-05:00", "Actual midnight end was lost"
    print(f"October 7 discoveries verified: {checked} upcoming additions; both October 6 events archived")


if __name__ == "__main__":
    verify(Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve())
