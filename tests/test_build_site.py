import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ORIGINAL_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_site", ORIGINAL_ROOT / "scripts" / "build_site.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BuildSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "assets").mkdir()
        (self.root / "assets" / "logo.png").write_bytes(b"logo")
        (self.root / "assets" / "favicon.svg").write_text("<svg></svg>")
        (self.root / "assets" / "event-fallback.webp").write_bytes(b"fallback")
        (self.root / "styles.css").write_text("body{}")
        (self.root / "app.js").write_text("\"use strict\";")
        artists = [
            {
                "name": "KB",
                "aliases": ["KB"],
                "enabled": True,
                "category": "core",
                "label": "HGA Music",
                "officialProfile": "https://www.whoiskb.com/",
                "instagramProfile": "https://www.instagram.com/kb_hga/",
            },
            {
                "name": "Hulvey",
                "aliases": ["Hulvey"],
                "enabled": True,
                "category": "reach",
            },
        ]
        events = [
            {
                "id": "kb-test-event",
                "title": "KB at Test Festival",
                "startDate": "2026-08-20",
                "startTime": "19:00",
                "venue": "Test Field",
                "city": "Sioux Falls",
                "state": "SD",
                "country": "US",
                "artists": ["KB"],
                "headliner": "KB",
                "eventType": "festival",
                "status": "scheduled",
                "officialUrl": "https://example.com/kb",
                "ticketUrl": "https://example.com/kb",
                "image": "https://example.com/kb.jpg",
                "sourceName": "Official festival",
                "lastVerified": "2026-08-10T12:00:00Z",
                "firstSeen": "2026-08-12T12:00:00Z",
            },
            {
                "id": "hulvey-test-event",
                "title": "Hulvey Live",
                "startDate": "2026-09-04",
                "startTime": "20:00",
                "venue": "Test Hall",
                "city": "Miami Beach",
                "state": "FL",
                "country": "US",
                "artists": ["Hulvey"],
                "headliner": "Hulvey",
                "eventType": "concert",
                "status": "scheduled",
                "officialUrl": "https://example.com/hulvey",
                "ticketUrl": "https://example.com/hulvey",
                "image": "",
                "sourceName": "Official venue",
                "lastVerified": "2026-08-10T12:00:00Z",
                "firstSeen": "2026-07-01T12:00:00Z",
            },
        ]
        (self.root / "config" / "artists.json").write_text(json.dumps(artists))
        (self.root / "events.json").write_text(json.dumps(events))
        (self.root / "run-status.json").write_text(json.dumps({
            "checkedAt": "2026-08-10T12:00:00Z",
            "warnings": ["source unavailable"],
            "errors": [],
        }))
        self.original_module_root = MODULE.ROOT
        MODULE.ROOT = self.root

    def tearDown(self):
        MODULE.ROOT = self.original_module_root
        self.temp.cleanup()

    def test_slugify_is_url_safe(self):
        self.assertEqual(MODULE.slugify("Torey D'Shaun — Live!"), "torey-d-shaun-live")

    def test_recent_window_is_fourteen_days(self):
        event = {"firstSeen": "2026-08-12T00:00:00Z"}
        self.assertTrue(MODULE.is_recent(event, date(2026, 8, 25)))
        self.assertFalse(MODULE.is_recent(event, date(2026, 8, 26)))

    def test_generates_real_multi_page_site(self):
        output = self.root / "_site"
        stats = MODULE.generate_site(output, today=date(2026, 8, 13))
        self.assertEqual(stats["events"], 2)
        self.assertEqual(stats["artists"], 2)
        self.assertTrue((output / "index.html").exists())
        self.assertTrue((output / "shows" / "index.html").exists())
        self.assertTrue((output / "shows" / "this-month" / "index.html").exists())
        self.assertTrue((output / "festivals" / "index.html").exists())
        self.assertTrue((output / "new-shows" / "index.html").exists())
        self.assertTrue((output / "artists" / "index.html").exists())
        self.assertTrue((output / "artists" / "kb" / "index.html").exists())
        self.assertTrue((output / "submit" / "index.html").exists())
        self.assertTrue((output / "states" / "south-dakota" / "index.html").exists())
        self.assertTrue(any((output / "shows").glob("*/index.html")))

    def test_homepage_uses_exact_mission_and_no_start_here_label(self):
        output = self.root / "_site"
        MODULE.generate_site(output, today=date(2026, 8, 13))
        homepage = (output / "index.html").read_text()
        mission = "The Kingdom Circuit exists to connect people with CHH music, concerts, festivals, and community so the music reaches farther and more people have the opportunity to hear the gospel."
        self.assertIn(mission, homepage)
        self.assertNotIn(">Start Here<", homepage)
        self.assertIn('class="menu-toggle"', homepage)
        self.assertIn('id="calendar"', homepage)

    def test_new_shows_page_only_contains_recent_event(self):
        output = self.root / "_site"
        MODULE.generate_site(output, today=date(2026, 8, 13))
        page = (output / "new-shows" / "index.html").read_text()
        self.assertIn("KB at Test Festival", page)
        self.assertNotIn("Hulvey Live", page)
        self.assertIn("Added August 12", page)

    def test_artist_page_has_no_biography_section(self):
        output = self.root / "_site"
        MODULE.generate_site(output, today=date(2026, 8, 13))
        page = (output / "artists" / "kb" / "index.html").read_text()
        self.assertIn("Upcoming KB Shows", page)
        self.assertIn("Official Website", page)
        self.assertNotIn("About KB", page)

    def test_event_page_has_music_event_schema(self):
        output = self.root / "_site"
        MODULE.generate_site(output, today=date(2026, 8, 13))
        pages = list((output / "shows").glob("*/index.html"))
        event_pages = [path for path in pages if path.parent.name != "this-month"]
        self.assertTrue(event_pages)
        combined = "\n".join(path.read_text() for path in event_pages)
        self.assertIn('"@type":"MusicEvent"', combined)
        self.assertIn("Official Details", combined)

    def test_source_warning_is_only_in_footer(self):
        output = self.root / "_site"
        MODULE.generate_site(output, today=date(2026, 8, 13))
        homepage = (output / "index.html").read_text()
        warning = "1 source checks were unavailable"
        self.assertIn(warning, homepage)
        self.assertGreater(homepage.index(warning), homepage.index('<footer class="site-footer">'))

    def test_submit_page_uses_formspree_without_public_email(self):
        output = self.root / "_site"
        MODULE.generate_site(output, today=date(2026, 8, 13))
        page = (output / "submit" / "index.html").read_text()
        self.assertIn("https://formspree.io/f/mljreawj", page)
        self.assertNotIn("84lorinw@gmail.com", page)


if __name__ == "__main__":
    unittest.main()
