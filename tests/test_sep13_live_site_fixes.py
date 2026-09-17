import json
import sys
import tempfile
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

    def test_jimmy_rock_miami_weather_reschedule_is_durable(self):
        import apply_sep13_requested_events as requested
        import build_seo_site as builder

        instagram = "https://www.instagram.com/p/DdXLDe-BpRK/"
        old_path = (
            "/event/jimmy-rock-s-rave-and-worship-the-worship-wawa-"
            "2026-09-18-miami-17834a/"
        )
        for path in (ROOT / "config" / "manual-events.json", ROOT / "events.json"):
            matches = [
                event for event in load(path)
                if identity(event) == "jimmy-rock-worship-wawa-miami-2026"
            ]
            self.assertEqual(1, len(matches), path)
            event = matches[0]
            self.assertEqual("2026-12-18", event.get("startDate"))
            self.assertEqual("2026-09-18", event.get("previousStartDate"))
            self.assertEqual("rescheduled", event.get("status"))
            self.assertEqual("Weather", event.get("rescheduleReason"))
            self.assertEqual(instagram, event.get("officialUrl"))
            self.assertIn(old_path, event.get("legacyEventPaths") or [])
            self.assertIn(
                instagram,
                {source.get("url") for source in event.get("sources") or []},
            )
            self.assertIn("postponed due to weather", event.get("notes", ""))

        wanted = requested.UPSERTS["jimmy-rock-worship-wawa-miami-2026"]
        self.assertEqual("2026-12-18", wanted["startDate"])
        self.assertEqual("Rescheduled", builder.event_status_label(wanted))
        self.assertIn("due to weather", builder.rescheduled_notice(wanted))
        schema = builder.event_schema(dict(wanted, id="manual:jimmy-rock-worship-wawa-miami-2026"))
        self.assertEqual("https://schema.org/EventRescheduled", schema["eventStatus"])
        self.assertEqual("2026-09-18", schema["previousStartDate"])

    def test_jimmy_rock_profile_uses_local_official_portrait(self):
        artist = next(a for a in load(ROOT / "config" / "artists.json") if a.get("name") == "JIMMY ROCK")
        self.assertEqual("assets/artists/jimmy-rock-primary.webp", artist.get("imageUrl"))
        self.assertEqual("center", artist.get("imagePosition"))
        portrait = ROOT / artist["imageUrl"]
        self.assertTrue(portrait.is_file(), portrait)
        self.assertGreater(portrait.stat().st_size, 10_000)

    def test_jimmy_rock_portrait_replaces_seo_placeholders(self):
        import apply_live_artist_overrides as overrides

        artist = next(a for a in load(ROOT / "config" / "artists.json") if a.get("name") == "JIMMY ROCK")
        with tempfile.TemporaryDirectory() as temporary:
            site = Path(temporary)
            directory = site / "artists" / "index.html"
            profile = site / "artists" / "jimmy-rock" / "index.html"
            directory.parent.mkdir(parents=True)
            profile.parent.mkdir(parents=True)
            directory.write_text(
                '<article class="artist-card" data-artist-card><a class="artist-visual artist-visual-empty" '
                'href="/artists/jimmy-rock/"></a><h2><a href="/artists/jimmy-rock/">JIMMY ROCK</a></h2></article>',
                encoding="utf-8",
            )
            profile.write_text(
                '<section class="seo-artist-hero"><div class="seo-profile-image seo-profile-placeholder" '
                'aria-hidden="true"></div><div class="profile-links"></div></section>',
                encoding="utf-8",
            )
            overrides.patch_static_artist_pages(site, [artist])
            self.assertIn('/assets/artists/jimmy-rock-primary.webp', directory.read_text(encoding="utf-8"))
            profile_html = profile.read_text(encoding="utf-8")
            self.assertIn('/assets/artists/jimmy-rock-primary.webp', profile_html)
            self.assertNotIn("seo-profile-placeholder", profile_html)

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
