from __future__ import annotations

import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import add_past_show_archives as archives


class LiveRedesignPromotionTests(unittest.TestCase):
    def test_deploy_pins_and_verifies_the_approved_redesign(self) -> None:
        workflow = (ROOT / ".github/workflows/update-and-deploy.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("APPROVED_REDESIGN_REF:", workflow)
        self.assertIn("66751f756158fae6c2682e34f7da12306bd133ab", workflow)
        self.assertIn("_redesign_source/scripts/apply_test_redesign.py", workflow)
        self.assertIn(
            "_redesign_source/test-overrides/assets/favicon-kc-stacked-v2-48.png",
            workflow,
        )
        self.assertIn(
            "_redesign_source/test-overrides/assets/favicon-kc-stacked-v2-maskable-512.png",
            workflow,
        )
        self.assertIn("--production", workflow)
        self.assertIn("--source-history event-history.json", workflow)
        self.assertIn("scripts/verify_live_redesign.py _site", workflow)

    def test_approved_seo_uses_the_production_visibility_cutoff(self) -> None:
        source = (ROOT / "scripts/apply_approved_seo.py").read_text(encoding="utf-8")
        self.assertIn("overlay.future = production_builder.current", source)
        self.assertIn('data-start-time="{start_time}"', source)

        builder = (ROOT / "scripts/build_seo_site.py").read_text(encoding="utf-8")
        self.assertIn("VISIBILITY_CUTOFF = TODAY", builder)
        self.assertNotIn("VISIBILITY_CUTOFF = TODAY -", builder)

        archive = (ROOT / "scripts/add_past_show_archives.py").read_text(encoding="utf-8")
        self.assertIn("PAST_GRACE_DAYS = 0", archive)

    def test_verifier_enforces_live_identity(self) -> None:
        source = (ROOT / "scripts/verify_live_redesign.py").read_text(encoding="utf-8")
        for token in (
            "kingdomcircuit.com",
            "G-N2KK9XF4TJ",
            "kingdom-circuit-test",
            "production",
            "current_808_count",
            "public-source-label",
            "favicon-kc-stacked-v2-48.png",
            "manifest.webmanifest",
        ):
            self.assertIn(token, source)

    def test_build_excludes_temporary_checkout_directories(self) -> None:
        source = (ROOT / "scripts/build_seo_site.py").read_text(encoding="utf-8")
        self.assertIn('"_seo_source"', source)
        self.assertIn('"_redesign_source"', source)

    def test_past_event_pages_preserve_verified_artwork(self) -> None:
        page = archives.past_page(
            ROOT,
            {
                "id": "past-artwork",
                "title": "Past Artwork Show",
                "startDate": "2026-09-01",
                "venue": "Example Hall",
                "city": "Chicago",
                "state": "IL",
                "artists": ["Hulvey"],
                "image": "assets/events/genesis-show-2026-all-women-v3.jpg",
                "imageType": "event_artwork",
            },
            {"hulvey"},
        )
        self.assertIn('class="event-detail-media"', page)
        self.assertIn('class="event-artwork"', page)
        self.assertIn('src="/assets/events/genesis-show-2026-all-women-v3.jpg"', page)

    def test_past_event_pages_upgrade_remote_images_to_https(self) -> None:
        page = archives.past_page(
            ROOT,
            {
                "id": "past-remote-artwork",
                "title": "Past Remote Artwork Show",
                "startDate": "2026-09-01",
                "venue": "Example Hall",
                "city": "Chicago",
                "state": "IL",
                "artists": ["Hulvey"],
                "image": "http://images.example.com/show.jpg",
                "imageType": "event_artwork",
            },
            {"hulvey"},
        )
        self.assertIn('src="https://images.example.com/show.jpg"', page)
        self.assertNotIn('src="http://images.example.com/show.jpg"', page)


if __name__ == "__main__":
    unittest.main()
