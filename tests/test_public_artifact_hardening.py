import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from harden_public_artifact import INTERNAL_FETCH_TARGETS, harden


class PublicArtifactHardeningTests(unittest.TestCase):
    def test_bulk_catalog_files_are_removed_but_static_site_remains(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            required = [
                "index.html", "styles.css", "robots.txt", "sitemap.xml", "CNAME",
                "shows/index.html", "artists/index.html", "festivals/index.html",
                "new-shows/index.html", "submit/index.html", "seo-enhancements.js",
            ]
            footer = '<div id="notice" class="footer-status" data-calendar-status hidden></div>'
            for rel in required:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"<html><body>{footer}</body></html>" if path.suffix == ".html" else "ok", encoding="utf-8")

            (root / "events.json").write_text("[]", encoding="utf-8")
            (root / "supplemental-events.json").write_text("[]", encoding="utf-8")
            (root / "run-status.json").write_text(json.dumps({"lastSuccessfulUpdate": "2026-09-11T15:03:32Z"}), encoding="utf-8")
            (root / "config").mkdir()
            (root / "config" / "artists.json").write_text("[]", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets" / "artist-filter-fix.js").write_text("legacy bulk loader", encoding="utf-8")

            result = harden(root)

            self.assertGreaterEqual(result["removedJsonFiles"], 4)
            self.assertFalse((root / "events.json").exists())
            self.assertFalse((root / "supplemental-events.json").exists())
            self.assertFalse((root / "config").exists())
            self.assertIn("Calendar updated:</strong> Sep 11, 2026", (root / "index.html").read_text(encoding="utf-8"))
            runtime = (root / "app.js").read_text(encoding="utf-8")
            for target in INTERNAL_FETCH_TARGETS:
                self.assertNotIn(target, runtime)
            self.assertIn("data-event-filters", runtime)
            self.assertIn("data-submission-form", runtime)


if __name__ == "__main__":
    unittest.main()
