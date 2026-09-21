from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import finalize_sep12_complete_closeout as closeout

APPROVED_CURRENT_LOGO = "/assets/logo-wordmark.svg?v=1"
MIKE_MALAGIES_APPROVED_IMAGE = "https://static.wixstatic.com/media/61a78b_7545031064f049a6843e4c7d0666886f~mv2.jpg/v1/fill/w_327%2Ch_491%2Cal_c%2Cq_80%2Cusm_0.66_1.00_0.01%2Cenc_avif%2Cquality_auto/61a78b_7545031064f049a6843e4c7d0666886f~mv2.jpg"


class September12CompleteCloseoutTests(unittest.TestCase):
    def test_unconfirmed_public_access_is_not_published_as_ordinary_concert(self):
        egr = {"id": "manual:egr-2026-09-12-corpus-christi-tx", "artists": ["EGR"]}
        daytime = {"id": "day", "title": "808 BEEZY — Live at RWG TOUR 2026", "artists": ["808 BEEZY"], "startTime": "14:10"}
        evening = {"id": "night", "title": "808 BEEZY — Live at RWG TOUR 2026", "artists": ["808 BEEZY"], "startTime": "19:00"}
        self.assertTrue(closeout.should_hide_public(egr))
        self.assertFalse(closeout.should_hide_public(daytime))
        self.assertFalse(closeout.should_hide_public(evening))

    def test_fabricated_flyers_are_replaced_or_reported_as_honest_fallback(self):
        for key, replacement in closeout.ARTWORK_REPLACEMENTS.items():
            self.assertNotIn(closeout.public_src(replacement["image"]), closeout.FAKE_ASSETS, key)
        mission = closeout.ARTWORK_REPLACEMENTS[("Mission and Special Guests", "2026-10-17")]
        self.assertEqual("artist", mission["imageType"])
        self.assertEqual("assets/artists/mission-primary.jpg", mission["image"])
        self.assertEqual(3, mission["classification"])

    def test_image_markup_has_responsive_and_exhaustion_safe_fallback(self):
        tag = closeout.patch_image_tag('<img class="artist-photo" src="https://example.com/a.jpg">', "https://example.com/a.jpg", "artist")
        self.assertIn('srcset="https://example.com/a.jpg 1200w"', tag)
        self.assertIn('sizes="(max-width: 900px) 100vw, 320px"', tag)
        self.assertIn('referrerpolicy="no-referrer"', tag)
        self.assertIn("kcFallbackUsed", tag)
        self.assertIn("this.onerror=null", tag)

    def test_accessibility_runtime_covers_drawer_filters_and_correction_mode(self):
        js = closeout.ACCESSIBILITY_JS
        self.assertIn("drawer.inert = closed", js)
        self.assertIn('e.key==="Escape"', js)
        self.assertIn("returnFocus?.focus", js)
        self.assertIn("aria-pressed", js)
        self.assertIn("aria-live", js)
        self.assertIn("What needs to be corrected? Include a supporting source.", js)

    def test_artwork_inventory_covers_every_public_json_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            events = [
                {"id": "one", "title": "A", "startDate": "2026-10-01", "image": "assets/event-fallback.webp", "imageType": "fallback"},
                {"id": "two", "title": "B", "startDate": "2026-10-02", "image": "https://example.com/b.jpg", "imageType": "event_artwork"},
            ]
            (root / "events.json").write_text(json.dumps(events), encoding="utf-8")
            (root / "supplemental-events.json").write_text("[]", encoding="utf-8")
            report = closeout.write_artwork_inventory(root)
            audit = json.loads((root / "artwork-audit.json").read_text(encoding="utf-8"))
            self.assertEqual(2, report["eventsInventoried"])
            self.assertEqual(2, len(audit))
            self.assertTrue(audit[0]["artworkStillNeeded"])

    def test_metadata_removes_completed_and_duplicate_breadcrumb_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            page = root / "index.html"
            page.write_text('''<html><head><title>X</title><meta name="description" content="D"><link rel="canonical" href="https://kingdomcircuit.com/"><script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[]}</script><script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[]}</script><script type="application/ld+json">{"@type":"MusicEvent","name":"X","eventStatus":"https://schema.org/EventCompleted","image":"assets/x.jpg"}</script></head><body><img src="assets/x.jpg"></body></html>''', encoding="utf-8")
            report = closeout.metadata_and_schema(root)
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("EventCompleted", text)
            self.assertEqual(1, text.count('"@type":"BreadcrumbList"'))
            self.assertIn('property="og:image" content="https://kingdomcircuit.com/assets/x.jpg"', text)
            self.assertGreaterEqual(report["duplicateBreadcrumbsRemoved"], 1)

    def test_user_approved_brand_and_mike_malagies_image_are_preserved(self):
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn(APPROVED_CURRENT_LOGO, home)
        self.assertNotIn("logo-wordmark", str(closeout.ARTWORK_REPLACEMENTS))

        artists = json.loads((ROOT / "config" / "artists.json").read_text(encoding="utf-8"))
        mike = next(item for item in artists if item.get("name") == "Mike Malagies")
        self.assertEqual(MIKE_MALAGIES_APPROVED_IMAGE, mike.get("imageUrl"))
        self.assertNotIn("mike malagies", {closeout.norm(key[0]) for key in closeout.ARTWORK_REPLACEMENTS})


if __name__ == "__main__":
    unittest.main()
