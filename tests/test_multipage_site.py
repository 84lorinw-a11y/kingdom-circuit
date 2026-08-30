import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class MultiPageProductionTests(unittest.TestCase):
    def test_required_pages_exist(self):
        for rel in [
            "index.html", "shows/index.html", "shows/this-month/index.html",
            "festivals/index.html", "new-shows/index.html", "artists/index.html",
            "artists/profile/index.html", "event/index.html", "submit/index.html",
            "404.html"
        ]:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_no_test_site_paths_in_production_pages(self):
        for page in ROOT.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("/kingdom-circuit-test/", text, str(page))
            self.assertNotIn("TEST SITE", text, str(page))

    def test_navigation_points_to_real_pages(self):
        expected = ["/shows/", "/shows/this-month/", "/festivals/", "/new-shows/", "/artists/", "/submit/"]
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        for href in expected:
            self.assertIn(f'href="{href}"', text)

    def test_homepage_copy_and_paths(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Find Christian hip-hop shows.", text)
        self.assertIn("The Kingdom Circuit exists to connect people with CHH music", text)
        self.assertIn("This Month", text)
        self.assertIn("Artists", text)
        self.assertIn("Festivals", text)
        self.assertIn("data-event-grid", text)

    def test_submit_form_uses_formspree(self):
        text = (ROOT / "submit/index.html").read_text(encoding="utf-8")
        self.assertIn("https://formspree.io/f/mljreawj", text)
        self.assertNotIn("84lorinw@gmail.com", text)

    def test_ga_is_on_every_public_page(self):
        for page in ROOT.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertIn("G-N2KK9XF4TJ", text, str(page))

    def test_artist_directory_uses_blank_images_and_verified_spotify(self):
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("artist-visual-empty", app)
        self.assertIn("77IKXFvO7SpWrq8hflrUXc", app)
        self.assertIn("Spotify link pending verification", app)
        # Search URLs may remain in the registry as research placeholders, but
        # the public link helper must require a direct Spotify artist profile.
        self.assertIn(r"open\.spotify\.com\/artist\/", app)
        self.assertIn("const directProfile", app)

    def test_808_beezy_verified_registry(self):
        artists = json.loads((ROOT / "config/artists.json").read_text(encoding="utf-8"))
        artist = next(item for item in artists if item.get("name") == "808 BEEZY")
        self.assertEqual(54, artist.get("rosterOrder"))
        self.assertEqual("https://www.808beezy.com/", artist.get("website"))
        self.assertEqual("https://www.instagram.com/808beezy/?hl=en", artist.get("instagramProfile"))
        self.assertEqual("https://open.spotify.com/artist/3CltJZLndpJKtpUyRVBB1k", artist.get("spotifyProfile"))
        self.assertEqual("https://www.youtube.com/@808_BEEZY", artist.get("youtubeProfile"))
        self.assertTrue(artist.get("sourceRegistryVerified"))

    def test_event_images_have_fixed_frame(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("aspect-ratio: 4 / 3", css)
        self.assertRegex(css, r"event-media img\.event-artwork[^{]*\{[^}]*object-fit:\s*contain")
        self.assertRegex(css, r"event-media img\.artist-photo[^{]*\{[^}]*object-fit:\s*cover")

    def test_supplemental_events_are_complete(self):
        events = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        self.assertEqual(len(events), len({event["id"] for event in events}))

        skema_events = [event for event in events if "Skema Boy" in event.get("artists", [])]
        self.assertEqual(13, len(skema_events))
        for event in skema_events:
            self.assertTrue(event["officialUrl"].startswith("https://"))
            self.assertEqual("Zauntee", event.get("headliner"))
            self.assertEqual("assets/artists/zauntee.webp", event.get("image"))

        # Completed shows are intentionally pruned from source data now, so the
        # old Hope Fest fixture must not be required forever. Instead, protect
        # the self-hosted images for current Rare of Breed and Genesis records.
        rare_events = [event for event in events if "Rare of Breed" in event.get("artists", [])]
        self.assertGreaterEqual(len(rare_events), 3)
        for event in rare_events:
            self.assertEqual("assets/artists/rare-of-breed-primary.jpg", event.get("image"))
            self.assertEqual("artist", event.get("imageType"))

        genesis = [
            event for event in events
            if event.get("id") == "bandsintown:108758638"
            or "the genesis show" in str(event.get("title") or "").casefold()
        ]
        self.assertEqual(1, len(genesis))
        self.assertEqual("assets/artists/yumiya-primary.jpg", genesis[0].get("image"))
        self.assertEqual("artist", genesis[0].get("imageType"))

        self.assertTrue((ROOT / "assets/artists/rare-of-breed-primary.jpg").is_file())
        self.assertTrue((ROOT / "assets/artists/yumiya-primary.jpg").is_file())
        rare_asset = ROOT / "assets/artists/rare-of-breed-primary.jpg"
        yumiya_asset = ROOT / "assets/artists/yumiya-primary.jpg"
        fallback_asset = ROOT / "assets/event-fallback.webp"
        self.assertGreater(rare_asset.stat().st_size, 10000)
        self.assertGreater(yumiya_asset.stat().st_size, 10000)
        self.assertNotEqual(rare_asset.read_bytes(), fallback_asset.read_bytes())
        self.assertNotEqual(yumiya_asset.read_bytes(), fallback_asset.read_bytes())
        self.assertEqual(b"\xff\xd8", rare_asset.read_bytes()[:2])
        self.assertEqual(b"\xff\xd8", yumiya_asset.read_bytes()[:2])

    def test_event_image_cache_busting_is_durable(self):
        finalizer = (ROOT / "scripts/finalize_live_event_images.py").read_text(encoding="utf-8")
        runtime = (ROOT / "assets/event-image-repair.js").read_text(encoding="utf-8")
        versioned = ROOT / "assets/event-image-repair-kc2050.js"
        self.assertTrue(versioned.is_file())
        self.assertIn('PRIMARY_CACHE_TOKEN = "kc-20260829-2050"', finalizer)
        self.assertIn('RUNTIME_SCRIPT_URL = "/assets/event-image-repair-kc2050.js"', finalizer)
        self.assertIn('data-kc-lock-primary', finalizer)
        self.assertIn('kcLockPrimary', runtime)
        self.assertIn('?v=kc-20260829-2050', runtime)


if __name__ == "__main__":
    unittest.main()
