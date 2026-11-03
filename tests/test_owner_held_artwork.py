import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_show_artwork as artwork
import verify_oct8_reviewed_discoveries as discoveries
import verify_sep26_requested_lineups as lineups


class OwnerHeldArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "source"
        self.site = Path(self.temp.name) / "site"
        for root in (self.source, self.site):
            (root / "config").mkdir(parents=True)
        self.pin = {"id": "held-show", "startDate": "2999-11-19",
                    "image": "assets/events/held.jpg", "imageType": "event_artwork"}
        self.seed = dict(self.pin, title="Held show", city="Dallas", state="TX", country="US",
                         artists=["Alex Jean"], advertisedBilling=["Alex Jean"],
                         editorialBatch="2026-10-08-reviewed-discoveries")
        self.retained = dict(copy.deepcopy(self.seed), id="manual:held-show")
        self.write("config/manual-events.json", [self.seed], self.source)
        self.write("event-history.json", {"events": [{"event": self.retained}]}, self.source)
        redeemed = next(row for row in json.loads((ROOT / "config/artists.json").read_text())
                        if row["name"] == "REDEEMED")
        for root in (self.source, self.site):
            self.write("config/artists.json", [redeemed], root)
        self.write("events.json", [], self.site)
        self.write("supplemental-events.json", [], self.site)
        image = self.site / self.pin["image"]
        image.parent.mkdir(parents=True)
        image.write_bytes(b"retained artwork fixture")
        (self.site / "shows").mkdir()
        (self.site / "shows/index.html").write_text("")

    def write(self, filename, data, root):
        (root / filename).write_text(json.dumps(data))

    def verify_artwork(self, holds=None):
        with patch.object(artwork, "ROOT", self.source, create=True), \
                patch.object(artwork, "PINS", [self.pin]), \
                patch.object(artwork, "OWNER_HELD_IDS", {"held-show"} if holds is None else holds, create=True):
            artwork.verify(self.site)

    def verify_discoveries(self):
        with patch.object(discoveries, "ROOT", self.source), \
                patch.object(discoveries, "OWNER_HELD_IDS", {"held-show"}, create=True):
            discoveries.verify(self.site)

    def verify_lineups(self, holds=None):
        with patch.object(lineups, "PATCHES", {"held-show": self.seed}), \
                patch.object(lineups, "OWNER_HELD_IDS", {"held-show"} if holds is None else holds, create=True):
            lineups.verify(self.site)

    def test_held_pin_with_exact_source_history_and_artwork_stays_unpublished(self):
        self.verify_artwork()

    def test_held_pin_requires_retained_manual_source(self):
        self.write("config/manual-events.json", [], self.source)
        with self.assertRaisesRegex(AssertionError, "retained held source"):
            self.verify_artwork()

    def test_held_pin_requires_retained_history(self):
        self.write("event-history.json", {"events": []}, self.source)
        with self.assertRaisesRegex(AssertionError, "retained held history"):
            self.verify_artwork()

    def test_held_pin_rejects_a_different_retained_date(self):
        self.write("config/manual-events.json", [dict(self.seed, startDate="2999-11-20")], self.source)
        with self.assertRaisesRegex(AssertionError, "retained held source"):
            self.verify_artwork()

    def test_held_pin_rejects_a_live_feed_leak(self):
        self.write("events.json", [self.retained], self.site)
        with self.assertRaisesRegex(AssertionError, "held event in public feed"):
            self.verify_artwork()

    def test_nonheld_missing_current_pin_still_blocks_publication(self):
        with self.assertRaisesRegex(AssertionError, "missing active event"):
            self.verify_artwork(holds=set())

    def test_discovery_verifier_allows_exact_registered_hold(self):
        self.verify_discoveries()

    def test_discovery_verifier_rejects_a_held_feed_leak(self):
        self.write("events.json", [self.retained], self.site)
        with self.assertRaisesRegex(AssertionError, "held event in public feed"):
            self.verify_discoveries()

    def test_lineup_verifier_allows_exact_registered_hold(self):
        self.verify_lineups()

    def test_lineup_verifier_rejects_a_held_feed_leak(self):
        self.write("events.json", [self.retained], self.site)
        with self.assertRaisesRegex(AssertionError, "held event in public feed"):
            self.verify_lineups()

    def test_lineup_verifier_still_rejects_a_missing_nonheld_show(self):
        with self.assertRaises(KeyError):
            self.verify_lineups(holds=set())
