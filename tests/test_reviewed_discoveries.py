import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reviewed", ROOT / "scripts/preserve_reviewed_discoveries.py")
reviewed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewed)


class ReviewedDiscoveriesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.approved = [e for e in json.loads((ROOT / "config/manual-events.json").read_text())
                         if e.get("editorialBatch") == reviewed.BATCH]
        (self.root / "config/manual-events.json").write_text(json.dumps(self.approved))

    def test_refresh_restores_eight_once_without_inventing_set_times(self):
        events = [{"id": "manual:" + e["id"], "startDate": e["startDate"],
                   "firstSeen": "2026-09-29T23:00:00Z", "startTime": "19:00"}
                  for e in self.approved]
        supplemental = [copy.deepcopy(events[0])]
        reviewed.apply(self.root, events, supplemental, today="2026-09-29")
        self.assertEqual(len(events), 8)
        self.assertEqual(supplemental, [])
        for event in events:
            self.assertEqual(event["firstSeen"], "2026-09-29T23:00:00Z")
            self.assertTrue(event["image"])
            if event["artists"] in [["EGR"], ["Kevi Morse"]]:
                self.assertEqual(event["startTime"], "")
                self.assertNotIn("startDateTime", event)
        snapshot = copy.deepcopy(events)
        reviewed.apply(self.root, events, supplemental, today="2026-09-29")
        self.assertEqual(events, snapshot)

    def test_cancellation_and_expiration_are_not_reversed(self):
        event = copy.deepcopy(self.approved[0])
        event.update(id="manual:" + event["id"], status="cancelled")
        events = [event]
        reviewed.apply(self.root, events, [], today="2026-09-29")
        self.assertEqual(next(e for e in events if e["id"] == event["id"])["status"], "cancelled")
        expired = []
        reviewed.apply(self.root, expired, [], today="2026-12-06")
        self.assertEqual(expired, [])

    def test_dallas_hold_is_scoped_and_preserves_orlando(self):
        dallas = dict(id="bandsintown:candidate", startDate="2026-11-19",
                      artists=["Alex Jean"], city="Dallas")
        other_day = dict(dallas, id="another-day", startDate="2026-11-20")
        events = [dallas, other_day]
        supplemental = [dict(dallas, id="axs:1626463")]
        reviewed.apply(self.root, events, supplemental, today="2026-09-29")
        self.assertFalse(any(reviewed.held_dallas_candidate(e) for e in events + supplemental))
        self.assertIn(other_day, events)
        self.assertTrue(any(e["artists"] == ["Alex Jean"] and e["city"] == "Orlando" for e in events))

    def test_oct7_discoveries_replace_provider_fragments_without_resetting_age(self):
        approved = [e for e in json.loads((ROOT / "config/manual-events.json").read_text())
                    if e.get("editorialBatch") == "2026-10-07-reviewed-discoveries"]
        (self.root / "config/manual-events.json").write_text(json.dumps(approved))
        candidates = [dict(e, id=e["sourceEventIds"][0], startTime="18:00",
                           firstSeen="2026-10-07T20:00:00Z")
                      for e in approved if e.get("sourceEventIds")]
        events = []
        reviewed.apply(self.root, events, candidates, today="2026-10-07")
        self.assertEqual(len(events), 7)
        self.assertEqual(candidates, [])
        brightpoint = next(e for e in events if e["city"] == "Markleville")
        self.assertEqual(brightpoint["startTime"], "19:00")
        self.assertEqual(brightpoint["artists"], ["Zauntee"])
        self.assertEqual(brightpoint["firstSeen"], "2026-10-07T20:00:00Z")
        kaden = next(e for e in events if e["city"] == "Huntington Beach")
        self.assertEqual(kaden["startTime"], "")
        self.assertEqual(kaden["doorsTime"], "18:30")
        snapshot = copy.deepcopy(events)
        reviewed.apply(self.root, events, candidates, today="2026-10-07")
        self.assertEqual(events, snapshot)

    def test_after_doves_calendar_day_preserves_actual_midnight_end(self):
        event = next(e for e in json.loads((ROOT / "config/manual-events.json").read_text())
                     if e["id"] == "after-doves-at-the-cg-nashville-2026-10-06")
        self.assertEqual(event["endDate"], "2026-10-06")
        self.assertEqual(event["endDateTime"], "2026-10-07T00:00:00-05:00")
        self.assertEqual(event["firstSeen"], "2026-09-28T22:09:27Z")
        patch = json.loads((ROOT / "config/sep26-requested-lineups.json").read_text())[event["id"]]
        self.assertEqual(patch["endDate"], event["endDate"])
        self.assertEqual(patch["endDateTime"], event["endDateTime"])


if __name__ == "__main__":
    unittest.main()
