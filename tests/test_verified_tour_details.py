import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_verified_content_overrides as overrides  # noqa: E402


class VerifiedTourDetailsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))

    def event(self, event_id):
        return next(item for item in self.events if item.get("id") == event_id)

    def test_minneapolis_show_uses_official_venue_and_time(self):
        event = self.event("official:8cf69c5c610dae61d590")
        self.assertEqual("First Avenue", event.get("venue"))
        self.assertEqual("18:30", event.get("startTime"))
        self.assertEqual("America/Chicago", event.get("timezone"))
        self.assertEqual(
            {
                "startTime": "18:30",
                "timezone": "America/Chicago",
                "venue": "First Avenue",
            },
            overrides.INDIE_TOUR_DETAILS[("2026-09-20", "Minneapolis")],
        )

    def test_indianapolis_show_uses_official_venue_and_time(self):
        event = self.event("official:9f793162ae1bb3cab7f3")
        self.assertEqual("HI-FI Annex", event.get("venue"))
        self.assertEqual("19:00", event.get("startTime"))
        self.assertEqual("America/Indiana/Indianapolis", event.get("timezone"))
        self.assertEqual(
            {
                "startTime": "19:00",
                "timezone": "America/Indiana/Indianapolis",
                "venue": "HI-FI Annex",
            },
            overrides.INDIE_TOUR_DETAILS[("2026-09-23", "Indianapolis")],
        )


if __name__ == "__main__":
    unittest.main()
