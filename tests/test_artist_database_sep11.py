import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIED_BLOCK = [
    "Datin",
    "Aasha Marie",
    "DJ Mykael V",
    "Heesun Lee",
    "Ryan Trey",
    "Jered Sanders",
    "Toschii",
    "Eli Montanna",
    "JWoodz",
    "Kaden Jordan",
]


class ArtistDatabaseSeptember11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artists = json.loads((ROOT / "config" / "artists.json").read_text())
        cls.updates = json.loads(
            (ROOT / "config" / "verified-artist-registry-updates.json").read_text()
        )
        cls.manual_events = json.loads(
            (ROOT / "config" / "manual-events.json").read_text()
        )
        cls.sources = json.loads((ROOT / "config" / "official-sources.json").read_text())
        module_path = ROOT / "scripts" / "update_events.py"
        spec = importlib.util.spec_from_file_location("update_events_sep11_test", module_path)
        cls.update_events = importlib.util.module_from_spec(spec)
        assert spec.loader
        sys.modules[spec.name] = cls.update_events
        spec.loader.exec_module(cls.update_events)

    def test_rows_135_through_144_match_the_sheet_order(self):
        block = sorted(
            (item for item in self.artists if 135 <= item["rosterOrder"] <= 144),
            key=lambda item: item["rosterOrder"],
        )
        self.assertEqual([item["name"] for item in block], VERIFIED_BLOCK)
        self.assertEqual([item["rosterOrder"] for item in block], list(range(135, 145)))

    def test_verified_socials_are_direct_artist_profiles(self):
        artists = {item["name"].casefold(): item for item in self.artists}
        for name in VERIFIED_BLOCK:
            artist = artists[name.casefold()]
            self.assertTrue(artist.get("sourceRegistryVerified"), name)
            self.assertRegex(artist.get("instagramProfile", ""), r"^https://www\.instagram\.com/[^/?#]+/?$")
            self.assertRegex(artist.get("spotifyProfile", ""), r"^https://open\.spotify\.com/artist/[A-Za-z0-9]+$")
            self.assertRegex(artist.get("youtubeProfile", ""), r"^https://(?:www\.|music\.)?youtube\.com/(?:@|channel/|user/)[^?#]+$")

    def test_parris_chariz_dallas_lineup_is_complete(self):
        event = next(
            item for item in self.manual_events
            if item["id"] == "parris-chariz-world-is-watching-dallas-2026"
        )
        self.assertEqual(event["startDate"], "2026-10-11")
        self.assertEqual(event["venue"], "AM/FM Backyard")
        self.assertEqual(
            event["artists"],
            ["Parris Chariz", "Toschii", "Eli Montanna", "JWoodz"],
        )

    def test_kaden_jordan_official_tour_dates_are_durable(self):
        expected = {
            ("2026-09-23", "Orlando"),
            ("2026-10-23", "New Port Richey"),
            ("2026-11-13", "Orlando"),
            ("2026-12-11", "Ocala"),
        }
        found = {
            (item["startDate"], item["city"])
            for item in self.manual_events
            if "Kaden Jordan" in item.get("artists", [])
        }
        self.assertTrue(expected.issubset(found))
        normalized = [
            self.update_events.normalize_manual_event(item, "2026-09-11T18:00:00Z")
            for item in self.manual_events
            if "Kaden Jordan" in item.get("artists", [])
        ]
        self.assertTrue(all(normalized))

        source = next(
            item for item in self.sources
            if item["name"] == "Kaden Jordan official tour / Songkick"
        )
        self.assertEqual(source["url"], "https://www.songkick.com/artists/10314485-kaden-jordan")
        self.assertTrue(source["enabled"])


if __name__ == "__main__":
    unittest.main()
