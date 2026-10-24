import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_show_artwork as artwork


class ArtworkGeographyTests(unittest.TestCase):
    def run_verification(self, rows):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / "config").mkdir()
            (site / "config/artists.json").write_text("[]")
            (site / "events.json").write_text(json.dumps(rows))
            (site / "supplemental-events.json").write_text("[]")
            with patch.object(artwork, "PINS", [{"id": "pinned-show", "startDate": "2999-01-01"}]):
                artwork.verify(site)

    def test_retained_out_of_scope_source_does_not_require_public_page(self):
        self.run_verification([{"id": "pinned-show", "startDate": "2999-01-01",
                                "state": "LND", "country": "GB"}])

    def test_missing_current_pin_still_fails_without_excluded_source(self):
        with self.assertRaisesRegex(AssertionError, "missing active event"):
            self.run_verification([])
