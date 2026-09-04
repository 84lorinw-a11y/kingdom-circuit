import json
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATED_NAMES = [
    "J J L",
    "Priest Jones",
    "Corincris",
    "F’rael",
    "Sis N Lil Bro",
    "Kaboose",
    "TRU-SERVA",
]


class ArtistDatabaseSeptember4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artists = json.loads((ROOT / "config" / "artists.json").read_text(encoding="utf-8"))
        cls.updates = json.loads((ROOT / "config" / "verified-artist-registry-updates.json").read_text(encoding="utf-8"))
        cls.events = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))

    def test_sheet_artist_changes_are_published_with_verified_profiles(self):
        artists = {artist["name"].casefold(): artist for artist in self.artists}
        for name in UPDATED_NAMES:
            artist = artists[name.casefold()]
            self.assertTrue(artist["sourceRegistryVerified"], name)
            self.assertEqual(artist["state"], "MN", name)
            for field in ("instagramProfile", "spotifyProfile", "youtubeProfile", "imageUrl"):
                self.assertTrue(artist.get(field), (name, field))

        self.assertEqual(
            artists["corincris"]["youtubeProfile"],
            "https://www.youtube.com/channel/UCF-g5-rykdXV5O5uEoz5ggA",
        )

    def test_new_registry_block_matches_sheet_order(self):
        source_names = [item["name"] for item in self.updates]
        self.assertEqual(source_names[-7:], UPDATED_NAMES)

        roster_names = [item["name"] for item in self.artists]
        self.assertEqual(roster_names[54:54 + len(source_names)], source_names)

    def test_tru_serva_verified_future_shows_are_present(self):
        if date.today() > date(2026, 10, 25):
            self.skipTest("The verified TRU-SERVA dates have passed and may be pruned")
        shows = {
            event["id"]: event
            for event in self.events
            if "TRU-SERVA" in (event.get("artists") or [])
        }
        self.assertEqual(shows["bandsintown:1040011561"]["startDate"], "2026-10-09")
        self.assertEqual(
            shows["supplemental:tru-serva-truth-tour-las-cruces-2026"]["startDate"],
            "2026-10-25",
        )


if __name__ == "__main__":
    unittest.main()
