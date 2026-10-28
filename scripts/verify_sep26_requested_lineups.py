"""Validate requested full bills and source links in the final public artifact."""
import html
import json
import re
from pathlib import Path

import build_seo_site as builder
from apply_sep26_requested_lineups import PATCHES


def verify(site: Path):
    primary = json.loads((site / "events.json").read_text())
    supplemental = json.loads((site / "supplemental-events.json").read_text())
    rows = builder.merge_events(primary, supplemental)
    by_id = {str(r["id"]).removeprefix("manual:"): r for r in rows}
    # Check reviewed records before the display merge can append performers
    # from a separate artist-calendar listing at the same venue and time.
    # The merged page, billing, schema and curated schedules are checked below.
    reviewed_by_id = {}
    for row in primary + supplemental:
        reviewed_by_id.setdefault(str(row["id"]).removeprefix("manual:"), row)
    roster = json.loads((site / "config/artists.json").read_text())
    curated = {a["name"] for a in roster if a.get("enabled") is not False}
    shows = (site / "shows/index.html").read_text()
    cards = re.findall(r'<article\b[^>]*data-event-card[^>]*>.*?</article>', shows, re.S)
    for event_id, wanted in PATCHES.items():
        if not builder.current(wanted):
            continue
        if builder.norm(wanted.get("status")) in {"cancelled", "canceled"}:
            seeds = json.loads((Path(__file__).resolve().parents[1] / "config/manual-events.json").read_text())
            archived = next(e for e in seeds if str(e.get("id")).removeprefix("manual:") == event_id
                            and e.get("startDate") == wanted["startDate"])
            assert archived.get("status") in {"cancelled", "canceled"}
            href = builder.event_path(archived)
            detail = (site / href.strip("/") / "index.html").read_text()
            assert 'https://schema.org/EventCancelled' in detail, (event_id, "missing cancellation archive")
            assert not any(f'href="{href}"' in card for card in cards), (event_id, "still upcoming")
            continue
        event = by_id[event_id]
        reviewed = reviewed_by_id[event_id]
        for key in ("startDate", "startTime", "title", "venue", "artists", "advertisedBilling", "hosts", "officialUrl", "ticketUrl"):
            if key in wanted:
                assert reviewed.get(key) == wanted[key], (event_id, key, reviewed.get(key))
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
        if wanted.get("hosts"):
            expected_hosts = "Hosted by " + " and ".join(wanted["hosts"])
            assert expected_hosts in html.unescape(detail) and expected_hosts in html.unescape(card), event_id
        schemas = [json.loads(s) for s in re.findall(r'<script type="application/ld\+json">(.*?)</script>', detail, re.S)]
        schema = next(s for s in schemas if s.get("@type") == "MusicEvent")
        if wanted.get("startDateTime"):
            assert schema["startDate"] == wanted["startDateTime"]
        performer_names = {performer["name"] for performer in schema["performer"]}
        for host in wanted.get("hosts", []):
            assert host not in performer_names, (event_id, "host listed as performer")
        for name in wanted.get("advertisedBilling", []):
            assert name in performer_names, (event_id, name, "schema")
        for old in wanted.get("legacyEventPaths", []):
            assert f'location.replace("{href}")' in (site / old.strip("/") / "index.html").read_text()
    print("Requested concert corrections verified: complete billing, curated schedules, start times, sources and redirects")
