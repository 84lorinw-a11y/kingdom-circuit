from __future__ import annotations

import pathlib
import sys
import tempfile
import datetime as dt
import json
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import archive_event_history as archive
import add_past_show_archives as past_archives


class EventHistoryArchiveTests(unittest.TestCase):
    def test_both_public_event_feeds_are_archived(self) -> None:
        self.assertEqual(
            ["events.json", "supplemental-events.json"],
            [path.name for path in archive.EVENT_FILES],
        )

    def test_same_event_id_has_a_stable_archive_key(self) -> None:
        event = {"id": "submitted:example", "title": "Example"}
        self.assertEqual("id:submitted:example", archive.archive_key(event))

    def test_known_silver_spring_provider_geocode_is_repaired(self) -> None:
        repaired = archive.canonicalize_known_event_identity(
            {
                "id": "bandsintown:108188679",
                "bandsintownEventId": "108188679",
                "title": "Hulvey at Fillmore Silver Spring",
                "startDate": "2026-09-08",
                "startTime": "18:30",
                "venue": "Fillmore Silver Spring",
                "city": "Spring Valley",
                "state": "DC",
                "artists": ["Hulvey"],
            }
        )
        self.assertEqual("Silver Spring", repaired["city"])
        self.assertEqual("MD", repaired["state"])
        self.assertEqual("19:00", repaired["startTime"])
        self.assertEqual(["Hulvey", "indie tribe.", "Kijan Boone"], repaired["artists"])

    def test_past_archive_respects_the_one_day_visibility_grace(self) -> None:
        today = dt.datetime.now(past_archives.PACIFIC).date()
        events = []
        for days_ago in (1, 2):
            event_date = today - dt.timedelta(days=days_ago)
            events.append(
                {
                    "observedOnOrAfterEventDate": True,
                    "event": {
                        "id": f"show-{days_ago}",
                        "title": f"Show {days_ago}",
                        "startDate": event_date.isoformat(),
                        "city": "Chicago",
                        "state": "IL",
                        "artists": ["Hulvey"],
                        "verifiedVersion": True,
                    },
                }
            )
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "config").mkdir()
            (root / "config/artists.json").write_text(
                json.dumps([{"name": "Hulvey"}]), encoding="utf-8"
            )
            (root / "event-history.json").write_text(
                json.dumps({"events": events}), encoding="utf-8"
            )
            selected, _ = past_archives.load_events(root)
        self.assertEqual(["show-2"], [event["id"] for event in selected])


if __name__ == "__main__":
    unittest.main()
