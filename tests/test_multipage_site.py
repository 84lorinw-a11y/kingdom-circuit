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
        self.assertNotIn("open.spotify.com/search/", app)

    def test_event_images_have_fixed_frame(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("aspect-ratio: 4 / 3", css)
        self.assertRegex(css, r"event-media img\.event-artwork[^{]*\{[^}]*object-fit:\s*contain")
        self.assertRegex(css, r"event-media img\.artist-photo[^{]*\{[^}]*object-fit:\s*cover")

    def test_skema_events_are_complete(self):
        events = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        self.assertEqual(13, len(events))
        self.assertEqual(13, len({event["id"] for event in events}))
        for event in events:
            self.assertIn("Skema Boy", event["artists"])
            self.assertTrue(event["officialUrl"].startswith("https://"))

if __name__ == "__main__":
    unittest.main()
