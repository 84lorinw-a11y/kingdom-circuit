import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from apply_oct6_show_audit import apply, patch_event, GLO_ID, OLD_GLO_ID, OLD_GLO_PATH
from catalog_removals import withheld_event
from apply_sep13_requested_events import patch_rows


class October6AccuracyTests(unittest.TestCase):
    def test_refresh_merges_duplicate_preserves_first_seen_and_holds_only_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config").mkdir()
            canonical = dict(id=GLO_ID, startDate="2026-11-14", status="cancelled",
                             firstSeen="2026-09-20", image="approved.jpg")
            duplicate = dict(id="manual:" + OLD_GLO_ID, startDate="2026-11-15",
                             status="scheduled", firstSeen="2026-09-13")
            held = dict(id="manual:cj-emulous-kickback-grand-prairie-2026",
                        startDate="2026-11-14", status="scheduled")
            separate = dict(id="manual:the-kickback-gospel-ready-grand-prairie-2026-10-10",
                            startDate="2026-10-10", status="scheduled")
            (root / "events.json").write_text(json.dumps([duplicate, held, separate]))
            (root / "supplemental-events.json").write_text(json.dumps([canonical]))
            (root / "config/manual-events.json").write_text(json.dumps([duplicate, held]))
            (root / "event-history.json").write_text(json.dumps({"events": [
                {"firstSeen": "2026-08-01", "event": canonical}, {"event": held}]}))
            # Exercise the real older writer that used to revive November 15.
            patch_rows(root / "events.json", False)
            apply(root)
            rows = json.loads((root / "events.json").read_text())
            old = next(e for e in rows if e["id"] == duplicate["id"])
            self.assertEqual((old["status"], old["mergedIntoId"]), ("merged", GLO_ID))
            self.assertFalse(any(withheld_event(e) for e in rows))
            self.assertEqual(next(e for e in rows if e["id"] == separate["id"]), separate)
            glo = json.loads((root / "supplemental-events.json").read_text())[0]
            self.assertEqual(glo["firstSeen"], "2026-08-01")
            self.assertEqual(glo["status"], "cancelled")
            self.assertEqual(glo["image"], "approved.jpg")
            self.assertIn(OLD_GLO_PATH, glo["legacyEventPaths"])
            before = {p: p.read_bytes() for p in root.rglob("*.json")}
            apply(root)
            self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_reimported_source_url_is_held_but_later_reschedule_is_not(self):
        row = dict(id="new-provider-id", startDate="2026-11-14",
                   officialUrl="https://www.cjemulous.com/event-details/the-kickback-w-cj-emulous?ref=calendar")
        self.assertTrue(withheld_event(row))
        row["startDate"] = "2026-12-14"
        self.assertFalse(withheld_event(row))

    def test_venue_reimport_repair_keeps_artwork_status_and_later_moves(self):
        row = dict(id="new-provider-id", startDate="2026-10-24", venue="Tour title",
                   officialUrl="https://www.ticketmaster.com/event/3A00636DD48C7831",
                   status="postponed", image="approved.jpg", firstSeen="2026-08-01")
        patch_event(row)
        self.assertEqual(row["venue"], "The Bronze Peacock at House of Blues Houston")
        self.assertEqual((row["status"], row["image"], row["firstSeen"]),
                         ("postponed", "approved.jpg", "2026-08-01"))
        row.update(startDate="2026-12-24", venue="Later confirmed venue")
        before = copy.deepcopy(row)
        patch_event(row)
        self.assertEqual(row, before)


if __name__ == "__main__":
    unittest.main()
