#!/usr/bin/env python3
"""Verify these repairs survive all production overlays and the pinned redesign."""
import hashlib
import html
import json
from pathlib import Path
import re
import sys

import apply_egr_bizzle_updates as repair
import build_seo_site as builder


def uses_image(text: str, site: Path, original: str) -> bool:
    digest = hashlib.sha256((site / original).read_bytes()).hexdigest()[:24]
    return any(original in tag or f"/assets/optimized/{digest}-" in tag
               for tag in re.findall(r'<img\b[^>]*>', text))


def verify(site: Path) -> None:
    events = [row for name in ("events.json", "supplemental-events.json")
              for row in json.loads((site / name).read_text())]
    egr = next(a for a in json.loads((site / "config/artists.json").read_text()) if a["name"] == "EGR")
    assert egr["imagePosition"] == "50% 0%", "EGR portrait focal position lost"
    assert (site / repair.PORTRAIT).is_file(), "EGR portrait missing"
    profile = (site / "artists/egr/index.html").read_text()
    assert uses_image(profile, site, repair.PORTRAIT), "EGR profile still uses old image"
    assert repair.OLD_PORTRAIT not in profile
    bizzle_profile = (site / "artists/bizzle/index.html").read_text()
    assert uses_image(bizzle_profile, site, repair.BIZZLE_PORTRAIT), "Bizzle profile still uses broken image proxy"
    for source in repair.EVENTS:
        if not builder.current(source):
            continue
        matches = [row for row in events if repair.matches(row, source)]
        assert len(matches) == 1, (source["id"], "missing or duplicate event", len(matches))
        event = matches[0]
        for key in ("title", "artists", "advertisedBilling", "venue", "address", "startDate", "startTime", "doorsTime", "timezone", "officialUrl", "imageType"):
            assert event[key] == source[key], (source["id"], key)
        href = builder.event_path(event)
        detail = (site / href.strip("/") / "index.html").read_text()
        assert "event-artwork" in detail and uses_image(detail, site, source["image"]), (href, "wrong flyer")
        assert source["officialUrl"] in detail
        schemas = [json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', detail, re.S)]
        schema = next(s for s in schemas if s.get("@type") == "MusicEvent")
        assert schema["startDate"] == source["startDateTime"] and schema["endDate"] == source["endDateTime"], (href, "incorrect times")
        if source["city"] == "Chandler":
            assert "Oct 3–4" not in detail, "Midnight finish displayed as two-day event"
        line = re.search(r'<p class="artist-line">(.*?)</p>', detail, re.S)[1]
        assert all(name in html.unescape(line) for name in source["advertisedBilling"]), (href, "billing missing")
        for name in source["artists"]:
            artist_href = builder.artist_path(name)
            assert f'href="{artist_href}"' in line, (name, "artist link missing")
            artist_text = (site / artist_href.strip("/") / "index.html").read_text()
            assert href in artist_text, (name, "event missing from artist profile")
        for legacy in source["legacyEventPaths"]:
            old = (site / legacy.strip("/") / "index.html").read_text()
            assert f'location.replace("{href}")' in old, (legacy, "redirect missing")
            assert "December 18" not in old, (legacy, "wrong redirect notice")
        for path in ("index.html", "shows/index.html"):
            cards = re.findall(r'<article\b[^>]*data-event-card[^>]*>.*?</article>', (site / path).read_text(), re.S)
            card = next(card for card in cards if href in card)
            assert uses_image(card, site, source["image"]), (path, "wrong listing artwork")
            assert all(name in html.unescape(card) for name in source["advertisedBilling"]), (path, "billing missing")
    print("Final EGR/Bizzle content verified: portrait, official flyers, complete billing, shared listing and redirects")


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
