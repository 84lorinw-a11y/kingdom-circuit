"""Check reviewed event facts and duplicate suppression after the final overlay."""
import html
import json
import re
import sys
from pathlib import Path

from apply_oct6_show_audit import GLO_ID, OLD_GLO_ID, OLD_GLO_PATH, RUSLAN, key
from apply_sep26_approved_audit import ONE_DAY_BILL
from build_seo_site import current, event_path
from catalog_removals import withheld_event


def verify(site):
    rows = [e for name in ("events.json", "supplemental-events.json")
            for e in json.loads((site / name).read_text())]
    assert not any(withheld_event(e) for e in rows), "Conflicting Texas booking republished"
    assert not (site / "config/review-held-events.json").exists(), "Private review record published"
    by_id = {key(e): e for e in rows}
    shows = (site / "shows/index.html").read_text()
    cj = (site / "artists/cj-emulous/index.html").read_text()
    assert OLD_GLO_PATH not in shows and OLD_GLO_PATH not in cj
    assert "the-kickback-w-cj-emulous" not in shows and "the-kickback-w-cj-emulous" not in cj
    if OLD_GLO_ID in by_id:
        assert by_id[OLD_GLO_ID]["status"] == "merged"
        assert by_id[OLD_GLO_ID]["mergedIntoId"] == GLO_ID
    checked = []
    for event_id in [*RUSLAN, GLO_ID, "one-day-fall-festival-aurora-2026", "chh-takeover-huntington-2026-10-25"]:
        event = by_id.get(event_id)
        if event is None or not current(event):
            continue
        path = event_path(event)
        text = html.unescape((site / path.strip("/") / "index.html").read_text())
        schemas = [json.loads(s) for s in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)]
        schema = next(s for s in schemas if s.get("@type") == "MusicEvent")
        if event_id in RUSLAN:
            date, _, venue, _ = RUSLAN[event_id]
            if event["startDate"] == date:
                assert event["venue"] == venue and venue in text
                assert schema["location"]["name"] == venue
        elif event_id == GLO_ID:
            assert event["startDate"] == "2026-11-14" and event["startTime"] == "20:00"
            assert "CJ Emulous" in event["artists"]
            old = (site / OLD_GLO_PATH.strip("/") / "index.html").read_text()
            assert f'location.replace("{path}")' in old and f'https://kingdomcircuit.com{path}' in old
            assert path in cj
        elif event_id == "one-day-fall-festival-aurora-2026":
            assert event["advertisedBilling"] == ONE_DAY_BILL
            assert event["startTime"] == "16:30" and event["endTime"] == "20:05"
            assert "Evening Concert" in event["title"]
            assert all(name in text for name in ONE_DAY_BILL)
            assert "Serin Oh" not in text
            assert schema["endDate"] == "2026-10-10T20:05:00-06:00"
            for old_path in event["legacyEventPaths"]:
                old = (site / old_path.strip("/") / "index.html").read_text()
                assert f'location.replace("{path}")' in old
        else:
            assert "On This Rock" in event["advertisedBilling"]
            assert "Upon This Rock" not in text and "On This Rock" in text
        checked.append(path)
    print("October 6 reviewed venues, billing, evening concert and CJ duplicate reconciliation verified:", checked)


if __name__ == "__main__":
    verify(Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve())
