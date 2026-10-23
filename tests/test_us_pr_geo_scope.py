"""Regression checks for U.S./Puerto Rico publishing and curated venue provenance."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_seo_site import domestic_event, merge_events


class GeographyAndVenueGuards(unittest.TestCase):
    def test_only_us_and_puerto_rico_are_public(self):
        us = {"id": "test-us", "title": "US show", "startDate": "2027-01-01", "city": "Austin", "state": "TX", "country": "US", "artists": ["A"]}
        pr = {"id": "test-pr", "title": "PR show", "startDate": "2027-01-02", "city": "San Juan", "state": "PR", "country": "US", "artists": ["B"]}
        ca = {"id": "test-ca", "title": "Canada show", "startDate": "2027-01-03", "city": "Saskatoon", "state": "SK", "country": "CA", "artists": ["C"]}
        bad = {"id": "test-bad", "title": "Canada mislabeled", "startDate": "2027-01-04", "city": "Toronto", "state": "ON", "country": "US", "artists": ["D"]}
        self.assertTrue(domestic_event(us))
        self.assertTrue(domestic_event(pr))
        self.assertFalse(domestic_event(ca))
        self.assertFalse(domestic_event(bad))
        self.assertEqual({e["id"] for e in merge_events([us, ca], [pr, bad])}, {"test-us", "test-pr"})

    def test_browser_calendar_uses_same_guard(self):
        js = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("function isDomesticEvent(event)", js)
        self.assertIn("if (!isDomesticEvent(raw)) return;", js)
        self.assertIn('PR:"Puerto Rico"', js)

    def test_808_beezy_venues_and_original_first_seen(self):
        events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        supplemental = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        seeds = json.loads((ROOT / "config/artist-website-seed-events.json").read_text(encoding="utf-8"))
        for num, venue in {"108856031": "Indiana Tech", "108856562": "North Canton Chapel", "108856576": "North Canton Chapel"}.items():
            with self.subTest(num=num):
                published = next(e for e in events if e.get("id") == f"manual:808-beezy-bandsintown-{num}")
                source = next(e for e in supplemental if e.get("id") == f"manual:808-beezy-bandsintown-{num}")
                seed = next(e for e in seeds if e.get("id") == f"808-beezy-bandsintown-{num}")
                self.assertEqual((published["venue"], source["venue"], seed["venue"]), (venue, venue, venue))
                self.assertEqual(published["firstSeen"], "2026-09-02T14:46:37Z")
                self.assertEqual(source["firstSeen"], "2026-09-02T14:46:37Z")


if __name__ == "__main__":
    unittest.main()
