import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts import apply_approved_seo


ROOT = Path(__file__).resolve().parents[1]


class ApprovedSeoEventMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = apply_approved_seo.load_module(
            "kc_test_production_builder",
            ROOT / "scripts" / "build_seo_site.py",
        )

    def test_overlay_uses_production_identity_and_status_rules(self):
        primary = [
            {
                "id": "manual:fountain-fest-wv-2026",
                "title": "Fountain Fest WV 2026",
                "startDate": "2026-09-18",
                "startTime": "20:00",
                "venue": "Orr's Farm Market",
                "city": "Martinsburg",
                "state": "WV",
                "artists": ["Rare of Breed"],
                "status": "scheduled",
            },
            {
                "id": "manual:eventbrite:rare-of-breed-jacksonville-2026",
                "title": "Rare of Breed",
                "startDate": "2026-10-16",
                "startTime": "19:00",
                "venue": "Murray Hill Theatre",
                "city": "Jacksonville",
                "state": "FL",
                "artists": ["Rare of Breed"],
                "status": "cancelled",
            },
        ]
        supplemental = [
            {
                **primary[0],
                "id": "fountain-fest-wv-2026",
            },
            {
                **primary[1],
                "id": "eventbrite:rare-of-breed-jacksonville-2026",
                "status": "scheduled",
            },
            {
                "id": "supplemental:retired-tour-alias",
                "title": "Retired tour alias",
                "startDate": "2026-11-01",
                "city": "New York",
                "state": "NY",
                "artists": ["Example Artist"],
                "status": "merged",
            },
        ]

        events = apply_approved_seo.merge_production_events(
            self.builder,
            SimpleNamespace(future=lambda event: True),
            primary,
            supplemental,
        )

        self.assertEqual(["manual:fountain-fest-wv-2026"], [event["id"] for event in events])


class MultipageVerifierEventLinkTests(unittest.TestCase):
    REQUIRED = [
        "index.html",
        "shows/index.html",
        "shows/this-month/index.html",
        "festivals/index.html",
        "new-shows/index.html",
        "artists/index.html",
        "artists/profile/index.html",
        "event/index.html",
        "submit/index.html",
        "404.html",
        "styles.css",
        "app.js",
        "events.json",
        "run-status.json",
        "config/artists.json",
        "supplemental-events.json",
        "assets/logo.png",
        "assets/event-fallback.webp",
        "assets/artists/skema-boy.webp",
        "sitemap.xml",
    ]

    def test_broken_event_anchor_is_preserved_and_fails_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory)
            for relative in self.REQUIRED:
                path = site / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("placeholder", encoding="utf-8")

            artists = [{"name": "Mike Malagies"}] + [
                {"name": f"Test Artist {index}"} for index in range(298)
            ]
            (site / "config/artists.json").write_text(json.dumps(artists), encoding="utf-8")
            (site / "events.json").write_text("[]", encoding="utf-8")
            (site / "supplemental-events.json").write_text("[]", encoding="utf-8")
            (site / "run-status.json").write_text("{}", encoding="utf-8")
            (site / "app.js").write_text(
                "const VERIFIED_ARTIST_REGISTRY = {}; const ARTIST_OVERRIDES = {};",
                encoding="utf-8",
            )
            (site / "sitemap.xml").write_text(
                '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>',
                encoding="utf-8",
            )

            for relative in self.REQUIRED:
                if not relative.endswith(".html"):
                    continue
                path = site / relative
                page_path = "/" if relative == "index.html" else f"/{path.parent.relative_to(site)}/"
                path.write_text(
                    '<meta name="ga" content="G-N2KK9XF4TJ">'
                    f'<link rel="canonical" href="https://kingdomcircuit.com{page_path}">'
                    '<footer data-calendar-status></footer>',
                    encoding="utf-8",
                )

            broken_card = (
                '<article class="event-card">'
                '<a class="event-media" href="/event/missing-show/">'
                '<img src="/assets/event-fallback.webp" alt="Missing show">'
                "</a></article>"
            )
            index = site / "index.html"
            index.write_text(index.read_text(encoding="utf-8") + broken_card, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/verify_multipage_site.py"), str(site)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("Broken internal links remain", result.stderr + result.stdout)
            self.assertIn(
                '<a class="event-media" href="/event/missing-show/">',
                index.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
