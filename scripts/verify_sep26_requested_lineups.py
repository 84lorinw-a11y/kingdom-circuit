"""Validate requested full bills and source links in the final public artifact."""
import html
import json
import re
from pathlib import Path

import build_seo_site as builder
from apply_sep26_requested_lineups import PATCHES


def verify(site: Path):
    rows = builder.merge_events(json.loads((site / "events.json").read_text()),
                                json.loads((site / "supplemental-events.json").read_text()))
    by_id = {str(r["id"]).removeprefix("manual:"): r for r in rows}
    roster = json.loads((site / "config/artists.json").read_text())
    curated = {a["name"] for a in roster if a.get("enabled") is not False}
    shows = (site / "shows/index.html").read_text()
    cards = re.findall(r'<article\b[^>]*data-event-card[^>]*>.*?</article>', shows, re.S)
    for event_id, wanted in PATCHES.items():
        if not builder.current(wanted):
            continue
        event = by_id[event_id]
        for key in ("startDate", "startTime", "title", "venue", "artists", "advertisedBilling", "officialUrl", "ticketUrl"):
            if key in wanted:
                assert event.get(key) == wanted[key], (event_id, key, event.get(key))
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        card = next(c for c in cards if f'href="{href}"' in c)
        if wanted.get("officialUrl"):
            assert html.escape(wanted["officialUrl"], quote=True) in detail
        if wanted.get("advertisedBilling"):
            billing = html.unescape(re.search(r'<p class="artist-line">(.*?)</p>', detail, re.S)[1])
            assert all(n in billing and n in html.unescape(card) for n in wanted["advertisedBilling"]), event_id
            for name in wanted["artists"]:
                if name in curated:
                    profile = site / builder.artist_path(name).strip("/") / "index.html"
                    assert href in profile.read_text(), (event_id, name, "missing artist schedule")
        schemas = [json.loads(s) for s in re.findall(r'<script type="application/ld\+json">(.*?)</script>', detail, re.S)]
        schema = next(s for s in schemas if s.get("@type") == "MusicEvent")
        if wanted.get("startDateTime"):
            assert schema["startDate"] == wanted["startDateTime"]
        for name in wanted.get("advertisedBilling", []):
            assert name in json.dumps(schema["performer"], ensure_ascii=False), (event_id, name, "schema")
        for old in wanted.get("legacyEventPaths", []):
            assert f'location.replace("{href}")' in (site / old.strip("/") / "index.html").read_text()
    print("Requested concert corrections verified: complete billing, curated schedules, start times, sources and redirects")
