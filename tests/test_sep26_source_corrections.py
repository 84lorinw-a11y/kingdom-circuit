import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_sep26_source_corrections as repair
from finalize_seo_indexing_core import concert_start_only


class SourceCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.other = {"id": "other-mike-teezy", "artists": ["Mike Teezy"], "startDate": "2026-11-07", "venue": "Another venue"}
        self.old = {"id": "official:4e2fc5c7c02ab1d34b9e", "artists": ["Mike Teezy"], "startTime": "18:00"}
        self.oasis = {"id": "manual:" + repair.OASIS_ID, "startDate": "2026-09-26", "startTime": "20:00", "endDate": "2026-09-26", "firstSeen": "2026-09-01T00:00:00Z"}
        self.save("events.json", [self.other, self.old, self.oasis, dict(repair.CLEVELAND, startTime="19:30")])
        self.save("supplemental-events.json", [{"id": "supplemental:beyond-the-walls-3-brenno-2026"}])
        self.save("config/manual-events.json", [])
        self.save("event-history.json", {"summary": {"total": 2}, "events": [
            {"archiveKey": "old-mike", "firstSeenOnCalendar": "2026-08-20", "event": copy.deepcopy(self.old)},
            {"archiveKey": "oasis", "event": copy.deepcopy(self.oasis)}]})

    def save(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def read(self, path):
        return json.loads((self.root / path).read_text())

    def test_stale_collection_is_consolidated_without_removing_unrelated_show(self):
        repair.apply(self.root, "2026-09-26")
        events = self.read("events.json")
        self.assertIn(self.other, events)
        cleveland = [row for row in events if repair.identity(row) == repair.CLEVELAND_ID]
        self.assertEqual(1, len(cleveland))
        self.assertEqual("20:00", cleveland[0]["startTime"])
        self.assertEqual(["KB", "Brenno", "Taylor Wells", "Porsha Love"], cleveland[0]["advertisedBilling"])
        self.assertNotIn("Mike Teezy", cleveland[0]["artists"])
        self.assertEqual([], self.read("supplemental-events.json"))
        history = self.read("event-history.json")
        self.assertEqual("merged", history["events"][0]["event"]["status"])
        self.assertEqual("2026-08-20", history["events"][0]["firstSeenOnCalendar"])
        self.save("supplemental-events.json", [self.old])
        repair.apply(self.root, "2026-09-26")
        self.assertEqual(events, self.read("events.json"))

    def test_reschedule_preserves_age_links_and_history_and_is_idempotent(self):
        repair.apply(self.root, "2026-09-26")
        oasis = next(row for row in self.read("events.json") if repair.identity(row) == repair.OASIS_ID)
        self.assertEqual("2026-09-27T19:00:00-04:00", oasis["startDateTime"])
        self.assertEqual("2026-09-01T00:00:00Z", oasis["firstSeen"])
        self.assertNotIn("endDate", oasis)
        self.assertEqual("rescheduled", oasis["status"])
        self.assertTrue(oasis["legacyEventPaths"])
        self.assertEqual("2026-09-27", self.read("event-history.json")["events"][1]["event"]["startDate"])
        before = {str(p): p.read_bytes() for p in self.root.rglob("*.json")}
        repair.apply(self.root, "2026-09-26")
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*.json")})
        repair.apply(self.root, "2026-11-08")
        self.assertEqual([self.other], self.read("events.json"))

    def test_public_doors_cleanup_preserves_concert_start_and_official_link(self):
        start = '<div><dt>Date</dt><dd>Sep 27 - 7:00 PM</dd></div>'
        link = '<a href="https://example.com">Official details</a>'
        self.assertEqual(start + link, concert_start_only(start + '<div><dt>Doors</dt><dd>5:30 PM</dd></div>' + link))


if __name__ == "__main__":
    unittest.main()
