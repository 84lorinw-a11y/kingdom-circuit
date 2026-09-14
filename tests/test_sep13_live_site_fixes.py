import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
EVENT_FILES = (
    ROOT / "config" / "manual-events.json",
    ROOT / "events.json",
    ROOT / "supplemental-events.json",
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(event):
    return str(event.get("id") or "").removeprefix("manual:")


class September13LiveSiteFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_file = {path: load(path) for path in EVENT_FILES}
        cls.events = cls.by_file[ROOT / "events.json"]

    def live_event(self, event_id):
        matches = [event for event in self.events if identity(event) == event_id]
        self.assertEqual(1, len(matches), event_id)
        return matches[0]

    def assert_local_artwork(self, event_id, expected):
        event = self.live_event(event_id)
        self.assertEqual(expected, event.get("image"))
        self.assertEqual("event_artwork", event.get("imageType"))
        self.assertTrue(event.get("imageOverride"))
        asset = ROOT / expected
        self.assertTrue(asset.is_file(), asset)
        self.assertGreater(asset.stat().st_size, 10_000)

    def test_jimmy_rock_shows_use_official_show_artwork(self):
        expected = {
            "jimmy-rock-worship-wawa-miami-2026": "assets/events/jimmy-rock-worship-wawa-miami-2026.jpg",
            "jimmy-rock-rave-worship-centennial-2026": "assets/events/jimmy-rock-rave-worship-denver-2026.jpg",
            "boise-invasion-2026": "assets/events/boise-invasion-2026.jpg",
            "jimmy-rock-rave-worship-dallas-2026": "assets/events/jimmy-rock-rave-worship-dallas-2026.webp",
        }
        for event_id, artwork in expected.items():
            with self.subTest(event_id=event_id):
                self.assert_local_artwork(event_id, artwork)

    def test_jimmy_rock_profile_uses_local_official_portrait(self):
        artist = next(a for a in load(ROOT / "config" / "artists.json") if a.get("name") == "JIMMY ROCK")
        self.assertEqual("assets/artists/jimmy-rock-primary.webp", artist.get("imageUrl"))
        self.assertEqual("center", artist.get("imagePosition"))
        portrait = ROOT / artist["imageUrl"]
        self.assertTrue(portrait.is_file(), portrait)
        self.assertGreater(portrait.stat().st_size, 10_000)

    def test_petrina_and_reign_use_the_replacement_images(self):
        petrina = self.live_event("one-day-fall-festival-aurora-2026")
        self.assertEqual("assets/events/petrina-delacey-one-day-2026.jpg", petrina.get("image"))
        self.assertEqual("center", petrina.get("imagePosition"))
        self.assertGreater((ROOT / petrina["image"]).stat().st_size, 10_000)
        self.assert_local_artwork(
            "eventbrite:reign-volume-one-aasha-marie-brooklyn-2026",
            "assets/events/reign-volume-one-single-2026.jpg",
        )

    def test_mayia_buttons_use_organizer_and_fair_sites(self):
        boxyard = self.live_event("mayia-boxyard-saturdaze-2026")
        fair = self.live_event("mayia-nc-state-fair-2026")
        self.assertEqual(
            "https://boxyard.rtp.org/events/saturdaze-wattyandmayia-102026-295-435-108/",
            boxyard.get("officialUrl"),
        )
        self.assertEqual("https://www.ncagr.gov/divisions/ncstatefair", fair.get("officialUrl"))
        self.assertEqual(
            "https://www.ncagr.gov/divisions/ncstatefair/buy-tickets-now",
            fair.get("ticketUrl"),
        )
        for event in (boxyard, fair):
            self.assertNotIn("mayiawarren.org/go/bandsintown", event.get("officialUrl", ""))
            self.assertNotIn("mayiawarren.org/go/bandsintown", event.get("ticketUrl", ""))

    def test_kurtis_main_page_portraits_keep_his_head_in_frame(self):
        kurtis = [
            event for event in self.events + self.by_file[ROOT / "supplemental-events.json"]
            if "Kurtis Hoppie" in (event.get("artists") or [])
            and event.get("image") == "assets/artists/kurtis-hoppie-primary.jpg"
        ]
        self.assertTrue(kurtis)
        self.assertTrue(all(event.get("imagePosition") == "50% 4%" for event in kurtis))

    def test_cancelled_rare_of_breed_show_cannot_return_as_a_duplicate(self):
        matches = [
            event
            for rows in self.by_file.values()
            for event in rows
            if identity(event) == "eventbrite:rare-of-breed-jacksonville-2026"
        ]
        self.assertTrue(matches)
        self.assertTrue(all(event.get("status") == "cancelled" for event in matches))
        self.assertTrue(all(event.get("cancellationConfirmed") is True for event in matches))

    def test_scheduled_repair_chain_keeps_all_requested_fixes(self):
        import apply_sep13_content_repairs as content
        import apply_sep13_requested_events as requested
        import apply_sep13_requested_image_hotfix as image_hotfix
        import apply_verified_show_repairs as verified

        self.assertEqual(
            "assets/events/jimmy-rock-worship-wawa-miami-2026.jpg",
            requested.UPSERTS["jimmy-rock-worship-wawa-miami-2026"]["image"],
        )
        self.assertEqual(
            "assets/events/jimmy-rock-rave-worship-denver-2026.jpg",
            requested.UPSERTS["jimmy-rock-rave-worship-centennial-2026"]["image"],
        )
        self.assertEqual(
            "assets/events/jimmy-rock-rave-worship-dallas-2026.webp",
            requested.UPSERTS["jimmy-rock-rave-worship-dallas-2026"]["image"],
        )
        self.assertEqual(
            "assets/events/boise-invasion-2026.jpg",
            requested.UPSERTS["boise-invasion-2026"]["image"],
        )
        self.assertEqual(
            "assets/events/petrina-delacey-one-day-2026.jpg",
            image_hotfix.PINS["one-day-fall-festival-aurora-2026"]["image"],
        )
        self.assertEqual("assets/events/reign-volume-one-single-2026.jpg", verified.REIGN_IMAGE)
        rare = next(event for event in verified.VERIFIED if event["id"] == "eventbrite:rare-of-breed-jacksonville-2026")
        self.assertEqual("cancelled", rare["status"])
        self.assertTrue(rare["cancellationConfirmed"])
        self.assertNotIn(
            "mayiawarren.org/go/bandsintown",
            content.MAYIA_LINKS["mayia-boxyard-saturdaze-2026"]["officialUrl"],
        )


if __name__ == "__main__":
    unittest.main()
