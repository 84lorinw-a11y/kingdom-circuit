"""Verify the approved October 8 search results after all production writers."""
import html
import json
from pathlib import Path
import sys

import build_seo_site as builder
from catalog_removals import withheld_event
from verify_egr_bizzle_updates import uses_image

ROOT = Path(__file__).resolve().parents[1]
BATCH = "2026-10-08-reviewed-discoveries"


def verify(site):
    raw = [e for filename in ("events.json", "supplemental-events.json")
           for e in json.loads((site / filename).read_text())]
    assert not any(withheld_event(e) for e in raw), "An owner-withheld event reappeared"
    approved = [e for e in json.loads((ROOT / "config/manual-events.json").read_text())
                if e.get("editorialBatch") == BATCH]
    checked = 0
    for wanted in approved:
        if not builder.current(wanted):
            continue
        matches = [e for e in raw if str(e["id"]).removeprefix("manual:") == wanted["id"]]
        if not builder.scheduled(wanted):
            # Final public feeds intentionally contain upcoming shows only;
            # the existing event URL remains as the cancellation notice.
            assert not any(builder.scheduled(e) for e in matches), (wanted["id"], "reactivated")
            event = dict(wanted, id="manual:" + wanted["id"])
        else:
            assert len(matches) == 1, (wanted["id"], "missing or duplicated across feeds")
            event = matches[0]
        for field in ("title", "startDate", "startTime", "venue", "city", "state",
                      "artists", "advertisedBilling", "officialUrl", "ticketUrl"):
            assert event.get(field) == wanted.get(field), (wanted["id"], field)
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        assert uses_image(detail, site, wanted["image"]), (wanted["id"], "approved image")
        for name in wanted["advertisedBilling"]:
            assert name in html.unescape(detail), (wanted["id"], name)
        if not builder.scheduled(wanted):
            assert event.get("status") == wanted["status"], (wanted["id"], "status")
            assert "EventCancelled" in detail, (wanted["id"], "cancellation schema")
            assert href not in (site / "shows/index.html").read_text(), (wanted["id"], "cancelled show listed")
            for name in wanted["artists"]:
                profile = site / builder.artist_path(name).strip("/") / "index.html"
                assert href not in profile.read_text(), (wanted["id"], "cancelled artist schedule")
            checked += 1
            continue
        assert href in (site / "shows/index.html").read_text(), (wanted["id"], "show list")
        for name in wanted["artists"]:
            profile = site / builder.artist_path(name).strip("/") / "index.html"
            assert href in profile.read_text(), (wanted["id"], name, "artist schedule")
        if wanted.get("timePending"):
            assert not event.get("startDateTime"), (wanted["id"], "invented concert time")
        checked += 1

    kaden = next((e for e in raw if e.get("id") == "manual:kaden-jordan-2026-11-13-orlando"), None)
    if kaden and builder.current(kaden):
        assert kaden["artists"] == ["Kaden Jordan", "Christopher Syncere"]
        assert kaden["title"] == "Kaden Jordan — The Babytooth Experience"
        href = builder.event_path(kaden)
        assert href in (site / "artists/christopher-syncere/index.html").read_text()
        old = site / "event/kaden-jordan-live-2026-11-13-orlando-8aaa06/index.html"
        assert old.is_file() and href in old.read_text(), "Existing Kaden URL lost its redirect"

    artists = json.loads((site / "config/artists.json").read_text())
    redeemed = next(a for a in artists if a["name"] == "REDEEMED")
    assert redeemed["instagramProfile"] == "https://www.instagram.com/redeemedmuzic33/"
    monitored = next(a for a in json.loads((ROOT / "config/artists.json").read_text())
                     if a["name"] == "REDEEMED")
    assert monitored["bandsintownProfile"] == "https://www.bandsintown.com/a/15645685-redeemed"
    print(f"October 8 discoveries verified: {checked} approved events, artist schedules, sources, artwork and excluded event")


if __name__ == "__main__":
    verify(Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve())
