import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


class September13ContentRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        cls.supplemental = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        cls.artists = json.loads((ROOT / "config/artists.json").read_text(encoding="utf-8"))

    def event(self, suffix):
        return next(item for item in self.events if str(item.get("id", "")).removeprefix("manual:") == suffix)

    def test_kurtis_profile_and_event_crops_are_intentional(self):
        image = "assets/artists/kurtis-hoppie-primary.jpg"
        artist = next(item for item in self.artists if item.get("name") == "Kurtis Hoppie")
        self.assertEqual(image, artist["imageUrl"])
        self.assertEqual("50% 22%", artist["imagePosition"])
        kurtis_events = [item for item in self.events + self.supplemental if "Kurtis Hoppie" in (item.get("artists") or [])]
        self.assertTrue(kurtis_events)
        boise = [item for item in kurtis_events if str(item.get("id", "")).removeprefix("manual:") == "boise-invasion-2026"]
        self.assertTrue(boise)
        self.assertTrue(all(item.get("image") == "assets/events/boise-invasion-2026.jpg" for item in boise))
        portraits = [item for item in kurtis_events if item not in boise]
        self.assertTrue(portraits)
        self.assertTrue(all(item.get("image") == image for item in portraits))
        self.assertTrue(all(item.get("imagePosition") == "50% 4%" for item in portraits))

    def test_requested_events_are_published(self):
        mike = self.event("mike-malagies-florida-takeover-miami-2026")
        self.assertEqual((mike["startDate"], mike["startTime"], mike["city"]), ("2026-10-16", "19:00", "North Miami"))
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

    def test_cj_new_mainstream_identity_uses_distinct_direct_event_urls(self):
        import apply_sep13_content_repairs as repairs

        repairs.sanitize_requested_event_identity()
        miami = repairs.REQUESTED_UPSERTS["cj-emulous-new-mainstream-miami-2026-11-05"]
        jacksonville = repairs.REQUESTED_UPSERTS["cj-emulous-new-mainstream-jacksonville-2026-11-08"]
        self.assertNotEqual(miami["officialUrl"], jacksonville["officialUrl"])
        self.assertEqual("", miami.get("ticketUrl"))
        self.assertEqual("", jacksonville.get("ticketUrl"))
        for event in (miami, jacksonville):
            self.assertNotIn(
                "https://milesminnick.com/tour",
                {str(source.get("url") or "") for source in event.get("sources") or []},
            )


if __name__ == "__main__":
    unittest.main()
