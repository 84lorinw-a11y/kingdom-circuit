import json
import sys
import unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


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
        cls.manual = json.loads((ROOT / "config/manual-events.json").read_text(encoding="utf-8"))

    def event(self, suffix):
        matches = [item for item in self.events if str(item.get("id", "")).removeprefix("manual:") == suffix]
        if matches:
            self.assertEqual(1, len(matches), suffix)
            return matches[0]
        # Completed shows legitimately leave the upcoming feed. Keep verifying
        # their reviewed durable record; a missing future show must still fail.
        retained = [item for item in self.manual if str(item.get("id", "")).removeprefix("manual:") == suffix]
        self.assertEqual(1, len(retained), f'Missing reviewed event: {suffix}')
        cutoff = datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()
        last_date = retained[0].get('endDate') or retained[0]['startDate']
        self.assertLess(last_date, cutoff, f'Upcoming event missing from public feed: {suffix}')
        return retained[0]

    def test_expired_record_can_be_checked_without_republishing_it(self):
        self.events = []
        self.manual = [{'id':'rollover-fixture','startDate':'2000-01-01','city':'Verified city'}]
        self.assertEqual('Verified city', self.event('rollover-fixture')['city'])

    def test_missing_future_or_ongoing_event_still_fails(self):
        self.events = []
        for end in (None, '9999-12-31'):
            self.manual = [{'id':'future-fixture','startDate':'9999-01-01' if end is None else '2000-01-01','endDate':end}]
            with self.assertRaisesRegex(AssertionError, 'Upcoming event missing'):
                self.event('future-fixture')

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
        promised = [item for item in kurtis_events if item.get("id") == "bandsintown:108923215"]
        self.assertTrue(promised)
        self.assertTrue(all(item.get("image") == "assets/events/the-promised-vi-2026-11-20.jpg" for item in promised))
        self.assertTrue(all(item.get("imageType") == "event_artwork" for item in promised))
        portraits = [item for item in kurtis_events if item not in boise + promised]
        self.assertTrue(all(item.get("image") == image for item in portraits))
        self.assertTrue(all(item.get("imagePosition") == "50% 4%" for item in portraits))

    def test_requested_events_are_published(self):
        mike = self.event("mike-malagies-florida-takeover-miami-2026")
        self.assertEqual((mike["startDate"], mike["startTime"], mike["city"]), ("2026-10-16", "19:00", "North Miami"))
        universal = self.event("rock-the-universe-orlando-2027")
        self.assertEqual((universal["startDate"], universal["endDate"]), ("2027-01-22", "2027-01-23"))
        self.assertEqual(universal["performerDays"]["2027-01-22"], ["1K Phew", "DJ Bryce G"])
        self.assertEqual(universal["performerDays"]["2027-01-23"], ["gio.", "Torey D'Shaun", "DJ Bryce G"])

    def test_tribe_lineup_and_mission_image_are_durable(self):
        tribe = self.event("tribe-fest-rialto-2026")
        self.assertEqual(9, len(tribe["artists"]))
        self.assertIn("Yasmine Jinelle", tribe["artists"])
        mission = self.event("mission-friends-sacramento-2026")
        self.assertEqual("event_artwork", mission["imageType"])
        self.assertEqual("assets/events/mission-sacramento-2026-10-17.jpg", mission["image"])
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
