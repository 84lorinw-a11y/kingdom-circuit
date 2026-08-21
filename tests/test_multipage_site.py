import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MultiPageProductionTests(unittest.TestCase):
    def test_required_pages_exist(self):
        for relative in (
            "index.html",
            "shows/index.html",
            "festivals/index.html",
            "artists/index.html",
            "artists/profile/index.html",
            "event/index.html",
            "new/index.html",
            "submit/index.html",
        ):
            self.assertTrue((ROOT / relative).exists(), relative)

    def test_homepage_copy_and_paths(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Christian Hip-Hop Shows", text)
        self.assertIn("Find verified upcoming Christian hip-hop concerts", text)
        self.assertNotIn("kingdom-circuit-test", text)

    def test_navigation_points_to_real_pages(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/shows/"', text)
        self.assertIn('href="/artists/"', text)
        self.assertIn('href="/festivals/"', text)
        self.assertIn('href="/submit/"', text)

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
        # The registry can retain search URLs as research placeholders, but the
        # public link helper must only accept direct Spotify artist profiles.
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

    def test_no_test_site_paths_in_production_pages(self):
        for page in ROOT.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("kingdom-circuit-test", text, str(page))


if __name__ == "__main__":
    unittest.main()
