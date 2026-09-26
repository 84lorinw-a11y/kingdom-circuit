#!/usr/bin/env python3
"""Check the final published feed, schema, artwork, billing and legacy URLs."""
import html
import json
from pathlib import Path
import re
import sys

import apply_sep26_source_corrections as repair
import build_seo_site as builder
from verify_egr_bizzle_updates import uses_image


def verify(site: Path) -> None:
    rows = [row for name in ("events.json", "supplemental-events.json") for row in json.loads((site / name).read_text())]
    for identity, wanted in ((repair.OASIS_ID, repair.UPSERTS[repair.OASIS_ID]),
                             (repair.MIAMI_ID, repair.NEW_EVENTS[repair.MIAMI_ID]),
                             (repair.CLEVELAND_ID, repair.CLEVELAND)):
        if not builder.current(wanted):
            continue
        matching = [row for row in rows if repair.identity(row) == identity]
        assert len(matching) == 1, (identity, "missing/duplicate", len(matching))
        event = matching[0]
        for key in ("title", "startDate", "startTime", "artists", "advertisedBilling", "officialUrl"):
            assert event[key] == wanted[key], (identity, key)
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        assert wanted["officialUrl"] in detail
        billing = html.unescape(re.search(r'<p class="artist-line">(.*?)</p>', detail, re.S)[1])
        assert all(name in billing for name in wanted["advertisedBilling"]), (identity, "billing")
        schemas = [json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', detail, re.S)]
        schema = next(item for item in schemas if item.get("@type") == "MusicEvent")
        assert schema["startDate"] == wanted["startDateTime"], (identity, "schema start")
        for legacy in wanted["legacyEventPaths"]:
            redirect = (site / legacy.strip("/") / "index.html").read_text()
            assert f'location.replace("{href}")' in redirect, legacy
        if identity == repair.OASIS_ID:
            assert uses_image(detail, site, wanted["image"]) and 'event-artwork' in detail
            assert schema["eventStatus"].endswith("EventRescheduled")
            assert schema["previousStartDate"].startswith("2026-09-26")
        if identity == repair.CLEVELAND_ID:
            assert "Mike Teezy" not in billing
            assert href not in (site / "artists/mike-teezy/index.html").read_text()
        assert href not in (site / "new-shows/index.html").read_text(), (identity, "correction listed as new")
    for page in site.rglob("*.html"):
        assert not re.search(r'<dt>Doors(?: open)?</dt>', page.read_text(), re.I), page
    print("Final source corrections verified: starts, full billing, reschedule, flyer, discovery age and redirects")


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
