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
    roster = json.loads((site / "config/artists.json").read_text())
    curated = {builder.norm(artist["name"]): artist["name"]
               for artist in roster if artist.get("enabled") is not False}
    primary = json.loads((site / "events.json").read_text())
    supplemental = json.loads((site / "supplemental-events.json").read_text())
    rows = builder.merge_events(primary, supplemental)
    # Source artwork pins can outlive a change in public geography. Only exempt
    # an absent page when its actual retained source record is outside scope.
    excluded_ids = {str(row["id"]).removeprefix("manual:")
                    for row in primary + supplemental
                    if not builder.domestic_event(row)}
    by_id = {str(row["id"]).removeprefix("manual:"): row for row in rows}
    targets = {}
    for pin in PINS:
        event = by_id.get(pin["id"])
        if not event and builder.norm(pin.get("status")) in {"cancelled", "canceled"}:
            # Cancelled shows leave public discovery feeds but retain an archive
            # page and their approved artwork. Verify that page, not an active card.
            seeds = json.loads((Path(__file__).resolve().parents[1] / "config/manual-events.json").read_text())
            event = next((e for e in seeds if str(e.get("id")).removeprefix("manual:") == pin["id"]
                          and e.get("startDate") == pin["startDate"]), None)
        if not event:
            assert not builder.current(pin) or pin["id"] in excluded_ids, (pin["id"], "missing active event")
            continue
        assert event["startDate"] == pin["startDate"], (pin["id"], "date changed")
        image_path = event["image"].lstrip("/")
        digest = hashlib.sha256((site / pin["image"]).read_bytes()).hexdigest()[:24]
        assert image_path == pin["image"] or re.fullmatch(
            rf"assets/optimized/{digest}-w\d+\.webp", image_path
        ), (pin["id"], "feed image", {"actual": image_path, "approved": pin["image"], "approved_sha24": digest})
        assert event["imageType"] == pin["imageType"], (pin["id"], "image type")
        href = builder.event_path(event)
        targets[href] = pin
        text = (site / href.strip("/") / "index.html").read_text()
        if builder.norm(pin.get("status")) in {"cancelled", "canceled"}:
            assert event.get("status") in {"cancelled", "canceled"}
            assert 'https://schema.org/EventCancelled' in text, (pin["id"], "missing cancellation")
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
            # A formerly unlinked performer can later join the reviewed roster.
            # Validate the current roster instead of a historical five-person bill.
            for name in pin["advertisedBilling"]:
                canonical = curated.get(builder.norm(name))
                path = builder.artist_path(canonical or name)
                linked = f'href="{path}"' in billing
                assert linked == bool(canonical), (pin["id"], name, "curated profile link")
                if canonical:
                    assert (site / path.strip("/") / "index.html").is_file(), (name, "missing artist page")
            schemas = [json.loads(raw) for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S)]
            schema = next(s for s in schemas if s.get("@type") in {"MusicEvent", "Event", "Festival"})
            assert all(name in json.dumps(schema["performer"]) for name in pin["advertisedBilling"])
    checked_cards = 0
    for page in site.rglob("*.html"):
        for card in re.findall(r'<article\b[^>]*data-event-card[^>]*>.*?</article>', page.read_text(), re.S):
            href = re.search(r'href="(/event/[^\"]+)"', card)
            pin = targets.get(href[1]) if href else None
            if pin:
                assert builder.scheduled(pin), (page, pin["id"], "cancelled show in discovery")
                assert uses_image(card, site, pin["image"]), (page, pin["id"], "discovery artwork")
                if "advertisedBilling" in pin:
                    assert all(name in html.unescape(card) for name in pin["advertisedBilling"])
                checked_cards += 1
    print(f"Verified official artwork on {len(targets)} show pages and {checked_cards} discovery cards")


if __name__ == "__main__":
    import sys
    verify(Path(sys.argv[1]))
