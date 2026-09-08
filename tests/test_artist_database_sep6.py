import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEW_VERIFIED_BLOCK = [
    "VVS Big Rock",
    "Sway GTTB",
    "Kashh Kade",
    "RÆL The Artist",
    "JustChris",
    "Stovetop",
    "yumiya!",
    "Linga TheBoss",
    "Petrina DeLacey",
    "Queen Lee",
    "Biancallove",
    "Joz",
    "G.E.S.",
    "Yasmine Jinelle",
    "Lyric The Geenyus",
    "Afeni",
    "Alexus Snow",
    "Neisha Glow",
]


class ArtistDatabaseSeptember6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artists = json.loads((ROOT / "config" / "artists.json").read_text(encoding="utf-8"))
        cls.updates = json.loads((ROOT / "config" / "verified-artist-registry-updates.json").read_text(encoding="utf-8"))
        cls.events = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))

    def test_verified_rows_follow_sheet_order(self):
        source_names = [item["name"] for item in self.updates]
        block_start = source_names.index(NEW_VERIFIED_BLOCK[0])
        self.assertEqual(
            NEW_VERIFIED_BLOCK,
            source_names[block_start:block_start + len(NEW_VERIFIED_BLOCK)],
        )

        roster_names = [item["name"] for item in self.artists]
        self.assertEqual(source_names, roster_names[54:54 + len(source_names)])

    def test_verified_profiles_are_complete(self):
        artists = {artist["name"].casefold(): artist for artist in self.artists}
        for name in NEW_VERIFIED_BLOCK:
            artist = artists[name.casefold()]
            self.assertTrue(artist["sourceRegistryVerified"], name)
            for field in ("instagramProfile", "spotifyProfile", "youtubeProfile"):
                self.assertTrue(artist.get(field), (name, field))

    def test_genesis_show_links_every_added_performer(self):
        event = next(item for item in self.events if "the genesis show" in item["title"].casefold())
        expected = {
            "Petrina DeLacey", "Queen Lee", "Biancallove", "Joz", "G.E.S.",
            "yumiya!", "Yasmine Jinelle", "Linga TheBoss", "Lyric The Geenyus",
            "Afeni", "Alexus Snow", "Neisha Glow",
        }
        self.assertTrue(expected.issubset(set(event["artists"])))


if __name__ == "__main__":
    unittest.main()