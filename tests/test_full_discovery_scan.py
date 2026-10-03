import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_full_discovery_scan as full_scan


class FullDiscoveryScanTests(unittest.TestCase):
    def test_public_bandsintown_html_is_delegated(self):
        events, status = full_scan.delegated_bandsintown(
            {"name": "KB"}, None, None, None
        )
        self.assertEqual(events, [])
        self.assertEqual(status["status"], "delegated_to_structured_rest")
        self.assertEqual(status["source"], "Bandsintown")

    def test_structured_status_replaces_blocked_html_summary(self):
        merged = full_scan.merge_bandsintown_status(
            {"artistsChecked": 390, "bandsintown": {"resolved": 0}},
            {
                "artistsChecked": 390,
                "artistsResolved": 210,
                "rawUpcomingUSRows": 80,
                "newNonFestivalShowsPublished": 12,
                "festivalCandidatesHeld": 4,
                "requestErrors": 3,
            },
        )
        self.assertEqual(merged["bandsintown"]["discoveryMode"], "structured_rest")
        self.assertEqual(merged["bandsintown"]["resolved"], 210)
        self.assertEqual(merged["bandsintown"]["newEventsPublished"], 12)
        self.assertEqual(merged["bandsintownHtml"]["status"], "skipped_structured_rest_used")

    def test_structured_failure_is_reported_without_claiming_success(self):
        merged = full_scan.merge_bandsintown_status(
            {"artistsChecked": 390}, {}, "HTTPError: temporary outage"
        )
        self.assertEqual(merged["bandsintown"]["status"], "failed_preserved_prior")
        self.assertIn("temporary outage", merged["bandsintown"]["error"])


if __name__ == "__main__":
    unittest.main()
