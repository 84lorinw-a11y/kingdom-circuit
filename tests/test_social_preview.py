from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_social_preview as social_preview  # noqa: E402


GENERIC_PAGE = """<!doctype html><html><head>
<meta property="og:image" content="https://kingdomcircuit.com/assets/logo-wordmark.svg?v=1">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://kingdomcircuit.com/assets/logo-wordmark.svg?v=1">
</head><body><main>Visible homepage</main></body></html>"""

EVENT_PAGE = """<!doctype html><html><head>
<meta property="og:image" content="https://images.example.test/event.jpg">
<meta name="twitter:image" content="https://images.example.test/event.jpg">
</head><body><main>Visible event</main></body></html>"""

LEGACY_CARD_PAGE = """<!doctype html><html><head>
<meta property="og:image" content="https://kingdomcircuit.com/assets/social-preview.png">
<meta name="twitter:image" content="https://kingdomcircuit.com/assets/social-preview.png">
</head><body><main>Visible artist</main></body></html>"""

MIXED_EVENT_PAGE = """<!doctype html><html><head>
<meta property="og:image" content="https://images.example.test/event.jpg">
<meta name="twitter:image" content="https://kingdomcircuit.com/assets/logo-wordmark.svg?v=1">
</head><body><main>Visible mixed event</main></body></html>"""


class SocialPreviewTests(unittest.TestCase):
    def test_applies_approved_card_without_changing_visible_content(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = Path(raw)
            event_page = site / "event" / "sample" / "index.html"
            event_page.parent.mkdir(parents=True)
            artist_page = site / "artists" / "sample" / "index.html"
            artist_page.parent.mkdir(parents=True)
            (site / "index.html").write_text(GENERIC_PAGE, encoding="utf-8")
            event_page.write_text(EVENT_PAGE, encoding="utf-8")
            artist_page.write_text(LEGACY_CARD_PAGE, encoding="utf-8")

            report = social_preview.apply(site)

            homepage = (site / "index.html").read_text(encoding="utf-8")
            event = event_page.read_text(encoding="utf-8")
            artist = artist_page.read_text(encoding="utf-8")
            self.assertEqual(2, report["pagesUpdated"])
            self.assertEqual(2, report["defaultPreviewPages"])
            self.assertEqual(
                social_preview.meta_content(homepage, "og:image"),
                social_preview.SOCIAL_PREVIEW_URL,
            )
            self.assertEqual(
                social_preview.meta_content(homepage, "og:image:secure_url"),
                social_preview.SOCIAL_PREVIEW_URL,
            )
            self.assertEqual(
                social_preview.meta_content(homepage, "og:image:width"), "1200"
            )
            self.assertEqual(
                social_preview.meta_content(homepage, "og:image:height"), "630"
            )
            self.assertEqual(
                social_preview.meta_content(homepage, "twitter:image:alt"),
                social_preview.SOCIAL_PREVIEW_ALT,
            )
            self.assertEqual(
                social_preview.meta_content(event, "og:image"),
                "https://images.example.test/event.jpg",
            )
            self.assertEqual(
                social_preview.meta_content(artist, "og:image"),
                social_preview.SOCIAL_PREVIEW_URL,
            )
            self.assertIn("<main>Visible homepage</main>", homepage)
            self.assertIn("<main>Visible event</main>", event)
            self.assertIn("<main>Visible artist</main>", artist)
            self.assertEqual(
                social_preview.png_dimensions(site / social_preview.SOCIAL_PREVIEW_REL),
                social_preview.SOCIAL_PREVIEW_SIZE,
            )
            self.assertEqual(
                social_preview.sha256(site / social_preview.SOCIAL_PREVIEW_REL),
                social_preview.SOCIAL_PREVIEW_SHA256,
            )

            second_report = social_preview.apply(site)
            self.assertEqual(0, second_report["pagesUpdated"])

    def test_uses_production_identity_only(self) -> None:
        self.assertEqual(
            "https://kingdomcircuit.com/assets/social-preview-wordmark-20260917.png",
            social_preview.SOCIAL_PREVIEW_URL,
        )
        self.assertNotIn("github.io", social_preview.SOCIAL_PREVIEW_URL)

    def test_mixed_metadata_never_overwrites_specific_event_art(self) -> None:
        output, changed = social_preview.apply_to_html(
            MIXED_EVENT_PAGE,
            Path("event/mixed/index.html"),
        )
        self.assertFalse(changed)
        self.assertEqual(MIXED_EVENT_PAGE, output)
        self.assertEqual(
            "https://images.example.test/event.jpg",
            social_preview.meta_content(output, "og:image"),
        )


if __name__ == "__main__":
    unittest.main()
