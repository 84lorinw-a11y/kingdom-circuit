#!/usr/bin/env python3
"""Check submitted October shows in the final production artifact, after overlays."""
import datetime as dt
import html
import json
from pathlib import Path
import re
import sys

import apply_man_of_faith_joz_shows as submission
import build_seo_site as builder
from verify_egr_bizzle_updates import uses_image


def verify(site: Path) -> None:
    profile = (site / "artists/joz/index.html").read_text()
    assert uses_image(profile, site, "assets/artists/joz-spotify-primary.jpg"), "Joz profile uses blank image proxy"
    events = [r for name in ("events.json", "supplemental-events.json")
              for r in json.loads((site / name).read_text())]
    for source in submission.EVENTS:
        if not builder.current(source):
            continue
        matches = [r for r in events if submission.matches(r, source)]
        assert len(matches) == 1, (source["id"], "missing or duplicate", len(matches))
        event = matches[0]
        for key in ("title", "artists", "headliner", "advertisedBilling", "startDate", "startTime", "timezone", "venue", "address", "officialUrl", "imageType"):
            assert event[key] == source[key], (source["id"], key)
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        assert uses_image(detail, site, source["image"]), (href, "wrong flyer")
        assert source["officialUrl"] in detail
        schemas = [json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', detail, re.S)]
        schema = next(s for s in schemas if s.get("@type") == "MusicEvent")
        assert schema["startDate"] == source.get("startDateTime", source["startDate"]), (href, "wrong local date/time")
        if source.get("endDateTime"):
            assert schema["endDate"] == source["endDateTime"]
        if source.get("ageRestriction"):
            assert schema["typicalAgeRange"] == source["ageRestriction"]
            assert source["ageRestriction"] in detail
        line = re.search(r'<p class="artist-line">(.*?)</p>', detail, re.S)[1]
        assert all(name in html.unescape(line) for name in source["advertisedBilling"])
        if source.get("unconfirmedArtists"):
            assert event.get("unconfirmedArtists") == source["unconfirmedArtists"]
            assert 'unconfirmed' not in line.lower()
            assert not any(p.get("name") in source["unconfirmedArtists"] for p in schema.get("performer", []))
            assert schema.get("description") == source["publicDescription"]
            description = re.search(r'<meta name="description" content="([^"]+)"', detail)[1]
            assert html.unescape(description) == source["publicDescription"]
            assert 'unconfirmed' not in description.lower(), "Removed session note returned in SEO description"
        for name in source["artists"]:
            artist_href = builder.artist_path(name)
            assert f'href="{artist_href}"' in line, (href, "artist link missing")
            assert href in (site / artist_href.strip("/") / "index.html").read_text()
        assert '/artists/southside-joz/' not in line
        if not source["venue"]:
            assert "Venue to be announced" in detail
        listing_paths = ["shows/index.html", f"{builder.state_path(source['state']).strip('/')}/index.html"]
        # Public feeds remove firstSeen, so test New Shows against the reviewed discovery time.
        if (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(source["firstSeen"].replace("Z", "+00:00"))).total_seconds() < 7 * 86400:
            listing_paths.append("new-shows/index.html")
        for path in listing_paths:
            cards = re.findall(r'<article\b[^>]*data-event-card[^>]*>.*?</article>', (site / path).read_text(), re.S)
            card = next((c for c in cards if href in c), None)
            assert card, (path, "event absent", href)
            assert uses_image(card, site, source["image"]), (path, "wrong flyer")
            assert all(name in html.unescape(card) for name in source["advertisedBilling"])
            if source.get("unconfirmedArtists"):
                assert 'unconfirmed' not in card.lower(), (path, "removed session note returned")
            if source["artists"] == ["Joz"]:
                assert '<a href="/artists/joz/">Southside Joz</a>' in card
        assert builder.absolute(href) in (site / "sitemap.xml").read_text()
    print("Submitted shows verified: artwork, local dates, billing, artist links, listings and internal session metadata")


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
