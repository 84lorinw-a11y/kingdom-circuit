"""Editorial cancellations survive stale provider refreshes."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from preserve_reviewed_discoveries import apply


class ReviewedStatusTests(unittest.TestCase):
    def apply_record(self, status, provider_status):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            approved = {"id": "reviewed-show", "startDate": "2026-10-24",
                        "status": status, "editorialBatch": "2026-10-09-reviewed-discoveries",
                        "sourceEventIds": ["bandsintown:123"],
                        "firstSeen": "2026-10-09T02:00:00Z"}
            (root / "config/manual-events.json").write_text(json.dumps([approved]))
            events = [{"id": "bandsintown:123", "startDate": "2026-10-24",
                       "status": provider_status, "firstSeen": "2026-10-08T02:00:00Z"}]
            supplemental = [dict(events[0])]
            apply(root, events, supplemental, today="2026-10-09")
            return events, supplemental

    def test_confirmed_cancellation_overrides_and_deduplicates_stale_show(self):
        events, supplemental = self.apply_record("cancelled", "scheduled")
        self.assertEqual(len(events), 1)
        self.assertFalse(supplemental)
        self.assertEqual(events[0]["status"], "cancelled")
        self.assertEqual(events[0]["firstSeen"], "2026-10-08T02:00:00Z")

    def test_scheduled_approval_cannot_reactivate_cancelled_provider(self):
        events, _ = self.apply_record("scheduled", "cancelled")
        self.assertEqual(events[0]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
