"""Check source artwork after the complete production overlay pipeline."""
import html
import hashlib
import json
import re
from pathlib import Path

import build_seo_site as builder
from apply_verified_show_artwork import PINS
from verify_egr_bizzle_updates import uses_image


def verify(site: Path):
    rows = builder.merge_events(json.loads((site / "events.json").read_text()),
                                json.loads((site / "supplemental-events.json").read_text()))
    by_id = {str(row["id"]).removeprefix("manual:"): row for row in rows}
    targets = {}
    for pin in PINS:
        event = by_id.get(pin["id"])
        if not event:
            assert not builder.current(pin), (pin["id"], "missing active event")
            continue
        assert event["startDate"] == pin["startDate"], (pin["id"], "date changed")
        image_path = event["image"].lstrip("/")
        digest = hashlib.sha256((site / pin["image"]).read_bytes()).hexdigest()[:24]
        assert image_path == pin["image"] or re.fullmatch(
            rf"assets/optimized/{digest}-w\d+\.webp", image_path
        ), (pin["id"], "feed image")
        assert event["imageType"] == pin["imageType"], (pin["id"], "image type")
        href = builder.event_path(event)
        targets[href] = pin
        text = (site / href.strip("/") / "index.html").read_text()
        if pin.get("officialUrl"):
            assert event["officialUrl"] == pin["officialUrl"], (pin["id"], "primary source")
            assert event["ticketUrl"] == pin["ticketUrl"], (pin["id"], "ticket destination")
            assert html.escape(pin["officialUrl"], quote=True) in text, (pin["id"], "source link")
        media = re.search(r'<div\b[^>]*class="[^"]*event-detail-media[^>]*>.*?</div>', text, re.S)
        assert media and uses_image(media[0], site, pin["image"]), (pin["id"], "detail artwork")
        css = "event-artwork" if pin["imageType"] == "event_artwork" else "artist-photo"
        assert css in media[0], (pin["id"], "image framing")
        if "advertisedBilling" in pin:
            billing = html.unescape(re.search(r'<p class="artist-line">(.*?)</p>', text, re.S)[1])
            assert event["advertisedBilling"] == pin["advertisedBilling"]
            assert all(name in billing for name in pin["advertisedBilling"]), (pin["id"], "missing flyer performer")
            assert 'href="/artists/issac-mansfield/"' in billing
            for slug in ("josh-morgan", "dj-cam", "lev-nova", "junado"):
                assert f'/artists/{slug}/' not in billing, (slug, "invented curated profile")
            schemas = [json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)]
            schema = next(s for s in schemas if s.get("@type") == "MusicEvent")
            assert all(name in json.dumps(schema["performer"]) for name in pin["advertisedBilling"])
    checked_cards = 0
    for page in site.rglob("*.html"):
        for card in re.findall(r'<article\b[^>]*data-event-card[^>]*>.*?</article>', page.read_text(), re.S):
            href = re.search(r'href="(/event/[^\"]+)"', card)
            pin = targets.get(href[1]) if href else None
            if pin:
                assert uses_image(card, site, pin["image"]), (page, pin["id"], "discovery artwork")
                if "advertisedBilling" in pin:
                    assert all(name in html.unescape(card) for name in pin["advertisedBilling"])
                checked_cards += 1
    print(f"Verified official artwork on {len(targets)} show pages and {checked_cards} discovery cards")


if __name__ == "__main__":
    import sys
    verify(Path(sys.argv[1]))
