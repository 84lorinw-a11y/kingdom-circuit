import json
import re
import unittest
from datetime import date
from pathlib import Path

from scripts.apply_curated_catalog_policy import curate_event
from scripts.apply_live_artist_overrides import dedupe_bandsintown_event_cards, sync_artist_page_show_counts
from scripts.apply_verified_show_repairs import PINNED_EVENT_IMAGES, VERIFIED

ROOT = Path(__file__).resolve().parents[1]

class MultiPageProductionTests(unittest.TestCase):
    def test_required_pages_exist(self):
        for rel in [
            "index.html", "shows/index.html", "shows/this-month/index.html",
            "festivals/index.html", "new-shows/index.html", "artists/index.html",
            "artists/profile/index.html", "event/index.html", "submit/index.html",
            "404.html"
        ]:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_no_test_site_paths_in_production_pages(self):
        for page in ROOT.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertNotIn("/kingdom-circuit-test/", text, str(page))
            self.assertNotIn("TEST SITE", text, str(page))

    def test_navigation_points_to_real_pages(self):
        expected = ["/shows/", "/shows/this-month/", "/festivals/", "/new-shows/", "/artists/", "/submit/"]
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        for href in expected:
            self.assertIn(f'href="{href}"', text)

    def test_homepage_copy_and_paths(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Find Christian hip-hop shows.", text)
        self.assertIn("The Kingdom Circuit exists to connect people with CHH music", text)
        self.assertIn("This Month", text)
        self.assertIn("Artists", text)
        self.assertIn("Festivals", text)
        self.assertIn("data-event-grid", text)

    def test_submit_form_uses_formspree(self):
        text = (ROOT / "submit/index.html").read_text(encoding="utf-8")
        self.assertIn("https://formspree.io/f/mljreawj", text)
        self.assertNotIn("84lorinw@gmail.com", text)

    def test_ga_is_on_every_public_page(self):
        for page in ROOT.rglob("*.html"):
            text = page.read_text(encoding="utf-8")
            self.assertIn("G-N2KK9XF4TJ", text, str(page))

    def test_artist_directory_uses_blank_images_and_verified_spotify(self):
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertIn("artist-visual-empty", app)
        self.assertIn("77IKXFvO7SpWrq8hflrUXc", app)
        self.assertIn("Spotify link pending verification", app)
        self.assertIn(r"open\.spotify\.com\/artist\/", app)
        self.assertIn("const directProfile", app)

    def test_808_beezy_verified_registry(self):
        artists = json.loads((ROOT / "config/artists.json").read_text(encoding="utf-8"))
        artist = next(item for item in artists if item.get("name") == "808 BEEZY")
        self.assertEqual(54, artist.get("rosterOrder"))
        self.assertEqual("https://www.808beezy.com/", artist.get("website"))
        self.assertEqual("https://www.instagram.com/808beezy/?hl=en", artist.get("instagramProfile"))
        self.assertEqual("https://open.spotify.com/artist/3CltJZLndpJKtpUyRVBB1k", artist.get("spotifyProfile"))
        self.assertEqual("https://www.youtube.com/@808_BEEZY", artist.get("youtubeProfile"))
        self.assertTrue(artist.get("sourceRegistryVerified"))

    def test_jon_keith_uses_a_verified_existing_image(self):
        artists = json.loads((ROOT / "config/artists.json").read_text(encoding="utf-8"))
        artist = next(item for item in artists if item.get("name") == "Jon Keith")
        self.assertEqual(
            "https://music.apple.com/us/artist/jon-keith/1139914139",
            artist.get("officialImageSource"),
        )
        self.assertIn("mzstatic.com", artist.get("imageUrl", ""))

        events = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        event = next(item for item in events if item.get("id") == "bandsintown:1040178082")
        self.assertEqual(artist["imageUrl"], event.get("image"))

    def test_event_images_have_fixed_frame(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("aspect-ratio: 4 / 3", css)
        self.assertRegex(css, r"event-media img\.event-artwork[^{]*\{[^}]*object-fit:\s*contain")
        self.assertRegex(css, r"event-media img\.artist-photo[^{]*\{[^}]*object-fit:\s*cover")

    def test_yung_kriss_event_artwork_is_high_resolution_and_pinned(self):
        events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        truthx = [item for item in events if item.get("title") == "TruthX Concert 2026"]
        self.assertEqual(1, len(truthx))
        expected = {
            "TruthX Concert 2026": "assets/events/truthx-yung-kriss-2026.jpg",
            "HVO Fest 2026": "assets/events/hvo-fest-2026.jpg",
        }
        for title, image in expected.items():
            event = next(item for item in events if item.get("title") == title)
            self.assertEqual(image, event.get("image"))
            self.assertEqual("event_artwork", event.get("imageType"))
            self.assertTrue(event.get("imageOverride"))
            asset = ROOT / image
            self.assertGreater(asset.stat().st_size, 300_000)
            self.assertEqual(b"\xff\xd8", asset.read_bytes()[:2])

    def test_artist_directory_defaults_to_upcoming_shows(self):
        page = (ROOT / "artists/index.html").read_text(encoding="utf-8")
        app = (ROOT / "app.js").read_text(encoding="utf-8")
        self.assertRegex(page, r"data-has-shows-filter[^>]*\bchecked\b")
        self.assertIn("if (show) show.checked = true;", app)

    def test_rendered_bandsintown_duplicates_are_removed(self):
        card = '<article class="event-card"><a href="https://www.bandsintown.com/e/108879559">Show</a></article>'
        other = '<article class="event-card"><a href="https://www.bandsintown.com/e/108879547">Show</a></article>'
        cleaned = dedupe_bandsintown_event_cards(card + card + other)
        self.assertEqual(2, cleaned.count('<article class="event-card">'))

    def test_artist_summary_counts_match_rendered_cards(self):
        cards = '<article class="event-card"></article>' * 19
        summary = '<p class="seo-artist-summary">Kingdom Circuit currently lists 30 verified upcoming U.S. shows for 808 BEEZY.</p>'
        stat = '<span>Upcoming shows</span><strong>30</strong>'
        results = '<p class="results-count" data-artist-results-count>30 shows</p>'
        cleaned = sync_artist_page_show_counts(summary + stat + results + cards)
        self.assertIn('lists 19 verified upcoming U.S. shows', cleaned)
        self.assertIn('<strong>19</strong>', cleaned)
        self.assertIn('>19 shows</p>', cleaned)

    def test_reviewed_fall_shows_use_official_event_artwork(self):
        verified = {event["title"]: event for event in VERIFIED}
        self.assertEqual(5, len(PINNED_EVENT_IMAGES))
        for title, image in PINNED_EVENT_IMAGES.items():
            self.assertEqual(image, verified[title]["image"])
            self.assertEqual("event_artwork", verified[title]["imageType"])
            self.assertTrue(verified[title]["imageOverride"])
            self.assertGreater((ROOT / image).stat().st_size, 100_000)

    def test_supplemental_events_are_complete(self):
        events = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        self.assertEqual(len(events), len({event["id"] for event in events}))

        skema_events = [event for event in events if "Skema Boy" in event.get("artists", [])]
        self.assertEqual(13, len(skema_events))
        for event in skema_events:
            self.assertTrue(event["officialUrl"].startswith("https://"))
            self.assertEqual("Zauntee", event.get("headliner"))
            self.assertEqual("assets/artists/zauntee.webp", event.get("image"))

        rare_events = [event for event in events if "Rare of Breed" in event.get("artists", [])]
        for event in rare_events:
            if event.get("id") == "eventbrite:rare-of-breed-jacksonville-2026":
                self.assertEqual("assets/events/rare-of-breed-jacksonville-2026.jpg", event.get("image"))
            else:
                self.assertTrue(event.get("image"))

        genesis = [
            event for event in events
            if event.get("id") == "bandsintown:108758638"
            or "the genesis show" in str(event.get("title") or "").casefold()
        ]
        self.assertEqual(1, len(genesis))
        self.assertEqual(
            [
                "Petrina DeLacey",
                "Queen Lee",
                "Biancallove",
                "Joz",
                "G.E.S.",
                "yumiya!",
                "Yasmine Jinelle",
                "Amarah",
                "Linga TheBoss",
                "Lyric The Geenyus",
                "Afeni",
                "Alexus Snow",
                "Neisha Glow",
            ],
            genesis[0].get("artists"),
        )
        self.assertEqual("The Social House", genesis[0].get("venue"))
        self.assertEqual("https://gratedco.ticketspice.com/the-genesis-show-", genesis[0].get("officialUrl"))
        self.assertEqual("$35 GA / $55 VIP", genesis[0].get("price"))
        self.assertEqual("assets/events/genesis-show-2026-all-women-v3.jpg", genesis[0].get("image"))
        self.assertEqual("event_artwork", genesis[0].get("imageType"))

        self.assertTrue((ROOT / "assets/artists/rare-of-breed-primary.jpg").is_file())
        self.assertTrue((ROOT / "assets/artists/rare-of-breed-event-card.svg").is_file())
        self.assertTrue((ROOT / "assets/artists/yumiya-primary.jpg").is_file())
        genesis_asset = ROOT / "assets/events/genesis-show-2026-all-women-v3.jpg"
        self.assertTrue(genesis_asset.is_file())
        self.assertGreater(genesis_asset.stat().st_size, 10000)
        self.assertEqual(b"\xff\xd8", genesis_asset.read_bytes()[:2])

    def test_space_city_fest_has_current_lineup_and_artwork(self):
        events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        event = next(event for event in events if event.get("title") == "Space City Fest 2026")
        self.assertEqual(
            ["Lecrae", "Lizzie Morgan", "Miles Minnick", "Lin D"],
            event.get("artists"),
        )
        self.assertEqual("assets/events/space-city-fest-2026-lineup.webp", event.get("image"))
        self.assertTrue((ROOT / event["image"]).is_file())

    def test_genesis_official_details_survive_provider_refreshes(self):
        refreshed = curate_event({
            "id": "bandsintown:108758638",
            "title": "The Genesis Show – All Women's CHH Event",
            "artists": ["yumiya!"],
            "headliner": "yumiya!",
            "image": "assets/artists/yumiya-primary.jpg",
            "officialUrl": "https://www.bandsintown.com/e/108758638",
        })
        self.assertIsNotNone(refreshed)
        self.assertEqual("The Social House", refreshed.get("venue"))
        self.assertEqual("assets/events/genesis-show-2026-all-women-v3.jpg", refreshed.get("image"))
        self.assertEqual("event_artwork", refreshed.get("imageType"))
        self.assertEqual("https://gratedco.ticketspice.com/the-genesis-show-", refreshed.get("officialUrl"))
        self.assertEqual(13, len(refreshed.get("artists", [])))

    def test_immersion_festival_content_until_event_passes(self):
        events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        matches = [
            event for event in events
            if event.get("id") == "manual:immersion-music-festival-circleville-2026"
        ]
        if not matches:
            self.assertGreater(date.today(), date(2026, 9, 5))
            return
        event = matches[0]
        self.assertEqual(["1K Phew", "WHATUPRG"], event.get("artists"))
        self.assertEqual("2026-09-05", event.get("startDate"))
        self.assertEqual("Pickaway County Agriculture & Event Center", event.get("venue"))
        self.assertEqual("Free", event.get("price"))

    def test_marty_kuna_show_uses_solo_artist_image(self):
        events = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        matches = [event for event in events if event.get("id") == "supplemental:marty-project-nation-kuna-2026"]
        if not matches:
            self.assertGreater(date.today(), date(2026, 9, 10))
            return
        event = matches[0]
        self.assertEqual("https://i.scdn.co/image/ab6761610000e5eb3d2d9f74de93906d1f5996f3", event.get("image"))
        self.assertEqual("artist", event.get("imageType"))
        rare_asset = ROOT / "assets/artists/rare-of-breed-primary.jpg"
        yumiya_asset = ROOT / "assets/artists/yumiya-primary.jpg"
        fallback_asset = ROOT / "assets/event-fallback.webp"
        self.assertGreater(rare_asset.stat().st_size, 10000)
        self.assertGreater(yumiya_asset.stat().st_size, 10000)
        self.assertNotEqual(rare_asset.read_bytes(), fallback_asset.read_bytes())
        self.assertNotEqual(yumiya_asset.read_bytes(), fallback_asset.read_bytes())
        self.assertEqual(b"\xff\xd8", rare_asset.read_bytes()[:2])
        self.assertEqual(b"\xff\xd8", yumiya_asset.read_bytes()[:2])

    def test_event_image_cache_busting_is_durable(self):
        finalizer = (ROOT / "scripts/finalize_live_event_images.py").read_text(encoding="utf-8")
        runtime = (ROOT / "assets/event-image-repair.js").read_text(encoding="utf-8")
        versioned = ROOT / "assets/event-image-repair-kc2100.js"
        self.assertTrue(versioned.is_file())
        self.assertEqual(runtime, versioned.read_text(encoding="utf-8"))
        self.assertIn('PRIMARY_CACHE_TOKEN = "kc-20260829-2050"', finalizer)
        self.assertIn('RUNTIME_SCRIPT_URL = "/assets/event-image-repair-kc2100.js"', finalizer)
        self.assertIn('IMAGE_FIX_SCRIPT_URL = "/assets/image-fix.js?v=20260906-2"', finalizer)
        self.assertIn('data-kc-lock-primary', finalizer)
        self.assertIn('kcLockPrimary', runtime)
        self.assertIn('classList?.contains("event-artwork")', runtime)
        self.assertIn('!src.includes("event-fallback.webp")', runtime)
        self.assertIn('?v=kc-20260829-2050', runtime)

    def test_home_image_guard_preserves_multi_artist_event_artwork(self):
        homepage = (ROOT / "index.html").read_text(encoding="utf-8")
        guard = (ROOT / "assets/home-primary-image-guard.js").read_text(encoding="utf-8")
        image_fix = (ROOT / "assets/image-fix.js").read_text(encoding="utf-8")
        self.assertIn('image-fix.js?v=20260906-2', homepage)
        self.assertIn('home-primary-image-guard.js?v=20260906-home-3', homepage)
        self.assertIn('artistLine === item.artist', guard)
        self.assertIn('img.classList.contains("event-artwork")', guard)
        self.assertNotIn('artistLine.includes(item.artist)', guard)
        self.assertIn('event?.imageType === "event_artwork"', image_fix)
        self.assertIn('return kcOriginalEventImage(event)', image_fix)


if __name__ == "__main__":
    unittest.main()
