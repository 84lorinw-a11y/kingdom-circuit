import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class September13ContentRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        cls.supplemental = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        cls.artists = json.loads((ROOT / "config/artists.json").read_text(encoding="utf-8"))

    def event(self, suffix):
        return next(item for item in self.events if str(item.get("id", "")).removeprefix("manual:") == suffix)

    def test_kurtis_uses_verified_official_portrait_everywhere(self):
        image = "assets/artists/kurtis-hoppie-primary.jpg"
        artist = next(item for item in self.artists if item.get("name") == "Kurtis Hoppie")
        self.assertEqual(image, artist["imageUrl"])
        kurtis_events = [item for item in self.events + self.supplemental if "Kurtis Hoppie" in (item.get("artists") or [])]
        self.assertTrue(kurtis_events)
        self.assertTrue(all(item.get("image") == image for item in kurtis_events))

    def test_requested_events_are_published(self):
        mike = self.event("mike-malagies-florida-takeover-miami-2026")
        self.assertEqual((mike["startDate"], mike["startTime"], mike["city"]), ("2026-10-16", "18:30", "North Miami"))
        universal = self.event("rock-the-universe-orlando-2027")
        self.assertEqual((universal["startDate"], universal["endDate"]), ("2027-01-22", "2027-01-23"))
        self.assertEqual(universal["performerDays"]["2027-01-23"], ["gio.", "Torey D'Shaun"])

    def test_tribe_lineup_and_mission_image_are_durable(self):
        tribe = self.event("tribe-fest-rialto-2026")
        self.assertEqual(9, len(tribe["artists"]))
        self.assertIn("Yasmine Jinelle", tribe["artists"])
        mission = self.event("mission-friends-sacramento-2026")
        self.assertEqual("artist", mission["imageType"])
        self.assertEqual("assets/artists/mission-primary.jpg", mission["image"])
        self.assertTrue((ROOT / mission["image"]).is_file())


if __name__ == "__main__":
    unittest.main()
