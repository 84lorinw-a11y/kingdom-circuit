import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MindsetArkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artists = json.loads((ROOT / "config" / "artists.json").read_text(encoding="utf-8"))
        cls.supplemental = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))

    def test_180mindset_has_verified_profile_image(self):
        artist = next(row for row in self.artists if row.get("name") == "180MINDSET")
        self.assertIn("wcrx.colum.edu/sessions/2023/5/29/180mindset", artist["officialImageSource"])
        self.assertIn("images.squarespace-cdn.com", artist["imageUrl"])
        self.assertTrue(artist["preferArtistImage"])

    def test_180mindset_is_on_ark_of_worship(self):
        event = next(row for row in self.supplemental if row.get("id") == "ark-of-worship-2026")
        self.assertIn("180MINDSET", event["artists"])


if __name__ == "__main__":
    unittest.main()
