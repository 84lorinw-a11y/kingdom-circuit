import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_events
from apply_verified_event_overrides import PASSION_FEST_EVENT, preserve_passion_fest


class PassionFestPublicationTests(unittest.TestCase):
    def test_verified_manual_festival_survives_normal_publishing_filter(self):
        manual = json.loads((ROOT / "config/manual-events.json").read_text())
        row = next(e for e in manual if e["id"] == "passion-fest-ii-2026-charlotte")
        candidate = update_events.normalize_manual_event(row, "2026-09-29T15:14:40Z")
        published = update_events.finalize_event(candidate, {})
        self.assertIsNotNone(published)
        self.assertEqual(published["artists"], ["Queen Lee", "BigBreeze"])

    def test_refresh_preserves_billing_and_deduplicates_without_changing_other_shows(self):
        other = {"id": "other-show", "title": "Unrelated show"}
        events = [copy.deepcopy(other)]
        supplemental = [dict(PASSION_FEST_EVENT, id="passion-fest-ii-2026-charlotte")]
        preserve_passion_fest(events, supplemental)
        preserve_passion_fest(events, supplemental)
        self.assertEqual(events[0], other)
        self.assertEqual(len(events), 2)
        self.assertEqual(supplemental, [])
        self.assertEqual(events[1]["advertisedBilling"], ["XEEM", "Queen Lee", "Markel (formerly BigBreeze)"])
        self.assertTrue((ROOT / events[1]["image"]).is_file())

    def test_verified_poster_does_not_override_later_cancellation(self):
        cancelled = dict(PASSION_FEST_EVENT, status="cancelled")
        events = [copy.deepcopy(cancelled)]
        preserve_passion_fest(events, [])
        self.assertEqual(events, [cancelled])


if __name__ == "__main__":
    unittest.main()
