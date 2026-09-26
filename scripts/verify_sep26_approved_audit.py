"""Verify the selected audit fixes after every production overlay has run."""
import html
import json
import re
from pathlib import Path

import build_seo_site as builder
from apply_sep26_approved_audit import PATCHES
from verify_egr_bizzle_updates import uses_image


def verify(site: Path):
    # Use the publisher's canonical merge: raw supplemental aliases may share
    # a listing with a manual record and do not each get their own detail URL.
    rows = builder.merge_events(json.loads((site / "events.json").read_text()),
                                json.loads((site / "supplemental-events.json").read_text()))
    root = Path(__file__).resolve().parents[1]
    source_rows = [row for name in ("events.json", "supplemental-events.json")
                   for row in json.loads((root / name).read_text())]
    for event_id, wanted in PATCHES.items():
        matching = [r for r in rows if str(r.get("id", "")).removeprefix("manual:") == event_id]
        active_sources = [r for r in source_rows
                          if str(r.get("id", "")).removeprefix("manual:") == event_id and builder.current(r)]
        if active_sources:
            assert matching, (event_id, "missing active listing")
        for event in matching:
            href = builder.event_path(event)
            detail = (site / href.strip("/") / "index.html").read_text()
            for key in ("title", "city", "venue", "startTime", "advertisedBilling", "soldOut"):
                if key in wanted:
                    assert event.get(key) == wanted[key], (event_id, key, event.get(key))
            if "image" in wanted:
                assert uses_image(detail, site, wanted["image"]), (event_id, "detail artwork")
                assert 'class="event-artwork"' in detail, (event_id, "artwork contain treatment")
            if "advertisedBilling" in wanted:
                billing = html.unescape(re.search(r'<p class="artist-line">(.*?)</p>', detail, re.S)[1])
                assert all(name in billing for name in wanted["advertisedBilling"]), (event_id, "billing")
            schemas = [json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', detail, re.S)]
            schema = next(s for s in schemas if s.get("@type") == "MusicEvent")
            if "startDateTime" in wanted:
                assert schema["startDate"] == wanted["startDateTime"], (event_id, "schema time")
            if wanted.get("soldOut"):
                assert "<dd>Sold Out</dd>" in detail, (event_id, "visible sold out")
                assert schema["offers"]["availability"].endswith("SoldOut"), (event_id, "sold out schema")
            for legacy in wanted.get("legacyEventPaths", []):
                redirect = (site / legacy.strip("/") / "index.html").read_text()
                assert f'location.replace("{href}")' in redirect, (event_id, legacy)
            shows = (site / "shows/index.html").read_text()
            card = next(c for c in re.findall(r'<article\b[^>]*data-event-card[^>]*>.*?</article>', shows, re.S) if href in c)
            if wanted.get("soldOut"):
                assert '>Sold Out</span>' in card, (event_id, "listing sold out")
            if "image" in wanted:
                assert uses_image(card, site, wanted["image"]), (event_id, "listing artwork")
            if "advertisedBilling" in wanted:
                assert all(name in html.unescape(card) for name in wanted["advertisedBilling"]), (event_id, "listing billing")
            for name in wanted.get("artists", []):
                profile = site / builder.artist_path(name).strip("/") / "index.html"
                assert href in profile.read_text(), (event_id, name, "artist schedule")
    print("Approved first-50 audit changes verified: artwork, starts, venues, billing, sold out and redirects")
