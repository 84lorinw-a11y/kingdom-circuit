import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW_VERIFIED_BLOCK = [
    "Alex Jean",
    "gio.",
    "Torey D'Shaun",
    "GRITS",
    "NF",
    "Nic D",
    "Manafest",
    "Pastor Mike Jr.",
    "Nesk Only",
    "Futuristic",
    "Sondae",
    "Dee-1",
    "Kieran the Light",
    "Childlike CiCi",
    "Yung Kriss",
    "Eluzai",
    "tylerhateslife",
    "Gavin the HotRod",
    "S.B.G.",
    "Aha Gazelle",
    "LaNell Grant",
    "Mogli the Iceburg",
    "EmanuelDaProphet",
    "Reece Lache'",
]


class ArtistDatabaseSeptember9Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artists = json.loads(
            (ROOT / "config" / "artists.json").read_text(encoding="utf-8")
        )
        cls.updates = json.loads(
            (ROOT / "config" / "verified-artist-registry-updates.json").read_text(
                encoding="utf-8"
            )
        )
        cls.manual_events = json.loads(
            (ROOT / "config" / "manual-events.json").read_text(encoding="utf-8")
        )
        module_path = ROOT / "scripts" / "update_events.py"
        spec = importlib.util.spec_from_file_location("update_events_sep9_test", module_path)
        cls.update_events = importlib.util.module_from_spec(spec)
        assert spec.loader
        sys.modules[spec.name] = cls.update_events
        spec.loader.exec_module(cls.update_events)

    def test_rows_111_through_134_match_the_sheet_order(self):
        self.assertEqual(
            [item["rosterOrder"] for item in self.updates],
            list(range(55, 135)),
        )
        update_block = [item for item in self.updates if 111 <= item["rosterOrder"] <= 134]
        self.assertEqual([item["rosterOrder"] for item in update_block], list(range(111, 135)))
        self.assertEqual([item["name"] for item in update_block], NEW_VERIFIED_BLOCK)

        roster_block = sorted(
            (item for item in self.artists if 111 <= item["rosterOrder"] <= 134),
            key=lambda item: item["rosterOrder"],
        )
        self.assertEqual([item["name"] for item in roster_block], NEW_VERIFIED_BLOCK)

    def test_all_24_profiles_are_verified_and_direct(self):
        artists = {item["name"].casefold(): item for item in self.artists}
        for name in NEW_VERIFIED_BLOCK:
            artist = artists[name.casefold()]
            self.assertTrue(artist.get("sourceRegistryVerified"), name)
            self.assertTrue(artist.get("officialImageSource"), name)
            self.assertRegex(artist.get("instagramProfile", ""), r"^https://www\.instagram\.com/[^/?#]+/?$")
            self.assertRegex(artist.get("spotifyProfile", ""), r"^https://open\.spotify\.com/artist/[A-Za-z0-9]+$")
            self.assertRegex(artist.get("youtubeProfile", ""), r"^https://(?:www\.|music\.)?youtube\.com/(?:@|channel/|user/)[^?#]+$")

        self.assertEqual(
            artists["yung kriss"]["spotifyProfile"],
            "https://open.spotify.com/artist/3JCk8XWIBcpA10QeM5tkbP",
        )
        self.assertEqual(artists["nic d"]["instagramProfile"], "https://www.instagram.com/iamnicd/")
        self.assertFalse(artists["tylerhateslife"].get("socialSearchEnabled"))
        self.assertEqual(artists["tylerhateslife"].get("activeStatus"), "legacy")

    def test_verified_calendar_coverage_is_configured(self):
        updates = {item["name"]: item for item in self.updates}
        with_bandsintown = {
            "Alex Jean", "gio.", "Torey D'Shaun", "GRITS", "NF", "Nic D",
            "Manafest", "Pastor Mike Jr.", "Futuristic", "Sondae", "Dee-1",
            "Childlike CiCi", "Yung Kriss", "Eluzai", "Aha Gazelle",
            "LaNell Grant", "Mogli the Iceburg",
        }
        for name in with_bandsintown:
            self.assertRegex(
                updates[name].get("bandsintownProfile", ""),
                r"^https://www\.bandsintown\.com/a/\d+",
                name,
            )

    def test_three_verified_future_show_records_normalize(self):
        expected = {
            "hvo-fest-2026-los-angeles": ("2026-09-26", {"Yung Kriss", "Alex Jean"}),
            "passion-fest-ii-2026-charlotte": ("2026-10-11", {"Yung Kriss"}),
            "flavor-fest-2026-saturday-concerts": ("2026-11-07", {"Lecrae", "Yung Kriss"}),
        }
        records = {item["id"]: item for item in self.manual_events}
        for identifier, (start_date, artists) in expected.items():
            raw = records[identifier]
            event = self.update_events.normalize_manual_event(raw, "2026-09-09T12:00:00Z")
            self.assertIsNotNone(event, identifier)
            self.assertEqual(event["id"], f"manual:{identifier}")
            self.assertEqual(event["startDate"], start_date)
            self.assertTrue(artists.issubset(set(event["artists"])))
            self.assertEqual(event["confidence"], "high")


if __name__ == "__main__":
    unittest.main()
