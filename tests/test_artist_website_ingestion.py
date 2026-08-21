import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import collect_artist_website_events as collector
import sync_verified_artist_registry as registry_sync


class ArtistWebsiteIngestionTests(unittest.TestCase):
    def test_real_artist_website_is_eligible(self):
        artist = {"website": "https://www.808beezy.com/"}
        self.assertEqual("https://www.808beezy.com/", collector.eligible_website(artist))

    def test_search_and_social_urls_are_not_artist_websites(self):
        self.assertEqual("", collector.eligible_website({"website": "https://www.google.com/search?q=artist"}))
        self.assertEqual("", collector.eligible_website({"website": "https://www.instagram.com/example/"}))

    def test_verified_website_registry_has_broad_coverage(self):
        websites = json.loads((ROOT / "config" / "verified-artist-websites.json").read_text(encoding="utf-8"))
        artists = json.loads((ROOT / "config" / "artists.json").read_text(encoding="utf-8"))
        roster = {artist.get("name", "").casefold() for artist in artists}
        self.assertGreaterEqual(len(websites), 50)
        self.assertEqual(len(websites), len({name.casefold() for name in websites}))
        self.assertTrue(all(name.casefold() in roster for name in websites))
        self.assertTrue(all(url.startswith(("http://", "https://")) for url in websites.values()))
        self.assertTrue(all("google.com/search" not in url for url in websites.values()))

    def test_808_beezy_has_direct_calendar_profile(self):
        self.assertEqual(
            "https://www.bandsintown.com/a/792282-808-beezy",
            registry_sync.ARTIST.get("bandsintownProfile"),
        )

    def test_808_beezy_verified_seed_dates_exist(self):
        events = json.loads((ROOT / "config" / "artist-website-seed-events.json").read_text(encoding="utf-8"))
        self.assertEqual(17, len(events))
        self.assertEqual(17, len({event.get("id") for event in events}))
        self.assertTrue(all(event.get("artists") == ["808 BEEZY"] for event in events))
        self.assertTrue(all(event.get("startDate") and event.get("startTime") for event in events))
        self.assertTrue(all(event.get("city") and event.get("state") for event in events))
        self.assertTrue(all(
            event.get("officialUrl", "").startswith((
                "https://www.bandsintown.com/e/",
                "https://www.808beezy.com/beezylive",
            ))
            for event in events
        ))


if __name__ == "__main__":
    unittest.main()
