from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import apply_public_image_repairs as repairs  # noqa: E402
import verify_public_image_repairs as verifier  # noqa: E402


CJ = repairs.CJ_EMULOUS_SOURCE
HULVEY = (
    "https://s1.ticketm.net/dam/a/d4e/"
    "a49ecab3-089d-46ff-baa5-7942c994ed4e_SOURCE"
)


class PublicImageRepairsTests(unittest.TestCase):
    def build_site(self, root: Path) -> Path:
        site = root / "site"
        (site / "config").mkdir(parents=True)
        (site / "event" / "sample").mkdir(parents=True)
        (site / "assets" / "optimized").mkdir(parents=True)
        page = f'''<!doctype html><html><head><title>Production</title></head><body>
<article class="event-card" data-event-card><a class="event-media"><img class="event-artwork extra" src="{CJ}" style="color:red;object-position:center" width="1333" height="1333"></a></article>
<article class="event-card" data-event-card><a class="event-media"><img class="event-artwork" src="{HULVEY}" width="1600" height="900"></a></article>
</body></html>'''
        (site / "index.html").write_text(page, encoding="utf-8")
        (site / "event" / "sample" / "index.html").write_text(
            page,
            encoding="utf-8",
        )
        events = [
            {
                "id": "cj",
                "title": "CJ",
                "image": CJ,
                "imageType": "fallback",
                "imagePosition": "center",
                "officialUrl": "https://example.com/cj",
            },
            {
                "id": "hulvey",
                "title": "Hulvey",
                "image": HULVEY,
                "imageType": "event_artwork",
                "imagePosition": "center",
                "officialUrl": "https://example.com/hulvey",
            },
        ]
        (site / "events.json").write_text(
            json.dumps(events, indent=2) + "\n",
            encoding="utf-8",
        )
        (site / "supplemental-events.json").write_text(
            json.dumps(events, indent=2) + "\n",
            encoding="utf-8",
        )
        (site / "config" / "artists.json").write_text("[]\n", encoding="utf-8")
        (site / "assets" / "site-ux-repairs.css").write_text(
            """.event-card .event-media { aspect-ratio: 4 / 3 !important; }
.event-card .event-media img.artist-photo { object-fit: cover !important; }
.event-card .event-media img.event-artwork { object-fit: contain !important; }
""",
            encoding="utf-8",
        )
        (site / "assets" / "optimized" / "manifest.json").write_text(
            json.dumps(
                {
                    "scope": "kingdom-circuit-production",
                    "requestedWidths": [320, 640, 960, 1280],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return site

    def test_repairs_are_scoped_idempotent_and_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = self.build_site(Path(raw))
            first = repairs.apply(site)
            first_html = (site / "index.html").read_text(encoding="utf-8")
            first_events = (site / "events.json").read_text(encoding="utf-8")
            second = repairs.apply(site)
            second_html = (site / "index.html").read_text(encoding="utf-8")
            second_events = (site / "events.json").read_text(encoding="utf-8")

            self.assertEqual(first_html, second_html)
            self.assertEqual(first_events, second_events)
            self.assertEqual(4, first["eventCardImagesSized"])
            self.assertEqual(4, second["eventCardImagesSized"])
            self.assertEqual(2, first["jsonFilesChanged"])
            self.assertEqual(0, second["jsonFilesChanged"])
            self.assertIn(f'sizes="{repairs.CARD_SIZES}"', first_html)
            self.assertIn('class="extra artist-photo"', first_html)
            self.assertIn('data-kc-image-focal="cj-emulous"', first_html)
            self.assertIn("object-position:center top", first_html)
            self.assertIn('data-kc-image-focal="hulvey"', first_html)
            self.assertIn("object-position:50% 30%", first_html)

            values = json.loads(first_events)
            self.assertEqual("artist", values[0]["imageType"])
            self.assertEqual("center top", values[0]["imagePosition"])
            self.assertEqual("artist", values[1]["imageType"])
            self.assertEqual("50% 30%", values[1]["imagePosition"])
            self.assertNotIn("sourceName", values[0])
            self.assertNotIn("sources", values[0])

            failures, report = verifier.verify(site)
            self.assertEqual([], failures)
            self.assertEqual(
                {"cj-emulous": 2, "hulvey": 2},
                report["focalHtmlImages"],
            )
            self.assertEqual(
                {"cj-emulous": 2, "hulvey": 2},
                report["focalJsonRecords"],
            )

    def test_focal_only_prepares_metadata_before_optimization(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = self.build_site(Path(raw))
            report = repairs.apply(site, focal_only=True)
            output = (site / "index.html").read_text(encoding="utf-8")

            self.assertEqual("production-focal-preparation", report["scope"])
            self.assertEqual(0, report["eventCardImagesSized"])
            self.assertIn('data-kc-image-focal="cj-emulous"', output)
            self.assertIn('data-kc-image-focal="hulvey"', output)
            self.assertNotIn(repairs.CARD_SIZES, output)

            repairs.apply(site)
            final_output = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn(repairs.CARD_SIZES, final_output)

    def test_source_only_json_files_are_never_read_or_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = self.build_site(Path(raw))
            private_files = (
                site / "config" / "manual-events.json",
                site / "artist-website-events.json",
            )
            private_payload = json.dumps(
                {
                    "image": CJ,
                    "sources": [{"url": "https://private.example/source"}],
                    "internalNote": "not public",
                }
            )
            for path in private_files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(private_payload, encoding="utf-8")

            repairs.apply(site)

            for path in private_files:
                self.assertEqual(private_payload, path.read_text(encoding="utf-8"))

    def test_focal_metadata_survives_opaque_optimizer_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = self.build_site(Path(raw))
            repairs.apply(site, focal_only=True)
            replacements = {
                CJ: "/assets/optimized/cj-focal-w1280.webp",
                HULVEY: "/assets/optimized/hulvey-focal-w1280.webp",
            }
            for path in (
                site / "index.html",
                site / "event" / "sample" / "index.html",
            ):
                text = path.read_text(encoding="utf-8")
                for source, optimized in replacements.items():
                    text = text.replace(
                        f'src="{source}"',
                        f'src="{optimized}" srcset="{optimized.replace("w1280", "w320")} 320w, {optimized} 1280w"',
                    )
                path.write_text(text, encoding="utf-8")
            for path in (
                site / "events.json",
                site / "supplemental-events.json",
            ):
                text = path.read_text(encoding="utf-8")
                for source, optimized in replacements.items():
                    text = text.replace(source, optimized.lstrip("/"))
                path.write_text(text, encoding="utf-8")

            repairs.apply(site)
            failures, report = verifier.verify(site)

            self.assertEqual([], failures)
            self.assertEqual(4, report["optimizedFocalImagesEligibleFor1280"])
            self.assertEqual(4, report["optimizedFocalImagesWith1280"])

    def test_verifier_rejects_broken_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = self.build_site(Path(raw))
            repairs.apply(site)
            page = site / "index.html"
            page.write_text(
                page.read_text(encoding="utf-8").replace(repairs.CARD_SIZES, "320px", 1),
                encoding="utf-8",
            )
            manifest = site / verifier.OPTIMIZED_MANIFEST
            manifest.write_text(
                json.dumps(
                    {
                        "scope": "kingdom-circuit-production",
                        "requestedWidths": [320, 640, 960],
                    }
                ),
                encoding="utf-8",
            )

            failures, _ = verifier.verify(site)
            self.assertTrue(any(item.startswith("event-card-sizes:") for item in failures))
            self.assertIn("optimized-manifest-missing-1280", failures)

    def test_verifier_requires_each_approved_focal_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = self.build_site(Path(raw))
            replacement = "https://example.com/non-focal.jpg"
            for path in (
                site / "index.html",
                site / "event" / "sample" / "index.html",
                site / "events.json",
                site / "supplemental-events.json",
            ):
                path.write_text(
                    path.read_text(encoding="utf-8").replace(CJ, replacement),
                    encoding="utf-8",
                )
            repairs.apply(site)

            failures, _ = verifier.verify(site)
            self.assertIn("focal-html-missing:cj-emulous", failures)
            self.assertIn("focal-json-missing:cj-emulous", failures)
            self.assertNotIn("focal-html-missing:hulvey", failures)
            self.assertNotIn("focal-json-missing:hulvey", failures)

    def test_target_guard_rejects_git_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            site = self.build_site(Path(raw))
            (site / ".git").mkdir()
            with self.assertRaises(SystemExit):
                repairs.apply(site)


if __name__ == "__main__":
    unittest.main()
