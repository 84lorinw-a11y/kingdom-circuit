import importlib.util
import json
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_events.py"
SPEC = importlib.util.spec_from_file_location("update_events", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class UpdateEventsTests(unittest.TestCase):
    def test_normalize_name_handles_punctuation(self):
        self.assertEqual(MODULE.normalize_name("nobigdyl."), "nobigdyl")
        self.assertEqual(MODULE.normalize_name("Torey D'Shaun"), "torey d shaun")
        self.assertEqual(MODULE.normalize_name("Q-Flo"), "q flo")

    def test_non_show_filter(self):
        self.assertTrue(MODULE.is_non_show("Parking Pass Only - Forrest Frank"))
        self.assertTrue(MODULE.is_non_show("VIP Early Entry Package Add-On"))
        self.assertFalse(MODULE.is_non_show("Forrest Frank: The Jesus Generation Tour"))

    def test_merge_events_combines_artists_and_sources(self):
        first = {
            "id": "ticketmaster:1",
            "title": "Example Festival",
            "startDate": "2099-07-10",
            "startTime": "19:00",
            "venue": "Example Arena",
            "city": "Minneapolis",
            "state": "MN",
            "artists": ["Lecrae"],
            "ticketUrl": "https://tickets.example/1",
            "sources": [{"name": "Ticketmaster", "url": "https://tickets.example/1"}],
        }
        second = {
            "id": "official:2",
            "title": "Example Festival 2099",
            "startDate": "2099-07-10",
            "startTime": "19:00",
            "venue": "Example Arena",
            "city": "Minneapolis",
            "state": "MN",
            "artists": ["KB"],
            "officialUrl": "https://festival.example",
            "sources": [{"name": "Official", "url": "https://festival.example"}],
        }
        merged = MODULE.merge_events([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["artists"], ["KB", "Lecrae"])
        self.assertEqual(len(merged[0]["sources"]), 2)

    def test_jsonld_event_extraction(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "MusicEvent",
          "name": "Test Concert",
          "startDate": "2099-08-01T19:00:00-05:00",
          "location": {
            "@type": "Place",
            "name": "Test Venue",
            "address": {
              "@type": "PostalAddress",
              "addressLocality": "Minneapolis",
              "addressRegion": "MN",
              "addressCountry": "US"
            }
          },
          "performer": {"@type": "Person", "name": "KB"},
          "url": "https://example.com/test"
        }
        </script>
        </head></html>
        """
        parser = MODULE.JsonLdScriptParser()
        parser.feed(html)
        self.assertEqual(len(parser.scripts), 1)
        payload = json.loads(parser.scripts[0])
        events = list(MODULE.iter_event_objects(payload))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["name"], "Test Concert")

    def test_safe_url_rejects_javascript(self):
        self.assertEqual(MODULE.safe_url("javascript:alert(1)"), "")
        self.assertEqual(MODULE.safe_url("https://example.com"), "https://example.com")


if __name__ == "__main__":
    unittest.main()
