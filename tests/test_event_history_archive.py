from __future__ import annotations

import pathlib
import sys
import tempfile
import datetime as dt
import json
import re
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import archive_event_history as archive
import add_past_show_archives as past_archives


class EventHistoryArchiveTests(unittest.TestCase):
    def test_archived_requested_address_survives_final_indexing(self) -> None:
        from finalize_seo_indexing_core import finalize_requested_event_address
        event = next(e for e in json.loads((ROOT / "config/manual-events.json").read_text())
                     if e["id"] == "new-kids-on-the-block-concert-orlando-2026-10-16")
        event = dict(event, id="manual:" + event["id"])
        with tempfile.TemporaryDirectory() as tmp:
            page = past_archives.past_page(pathlib.Path(tmp), event, set())
        result = finalize_requested_event_address(page, past_archives.event_path(event))
        self.assertIn('data-kc-full-address="true"', result)
        self.assertIn('6881 West Colonial Drive<br>Orlando, FL 32818', result)

    def test_archive_preserves_country_without_inventing_missing_address(self) -> None:
        event = dict(id="canadian-show", title="Canadian show", startDate="2026-10-16",
                     city="Toronto", state="ON", country="CA", artists=["JJ Stone"])
        with tempfile.TemporaryDirectory() as tmp:
            page = past_archives.past_page(pathlib.Path(tmp), event, set())
        schema = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page).group(1))
        address = schema["location"]["address"]
        self.assertEqual(address["addressCountry"], "CA")
        self.assertNotIn("streetAddress", address)
        self.assertNotIn("postalCode", address)

    def test_rejected_identity_cannot_return_from_current_saved_or_git_history(self) -> None:
        bad = {"id": "bandsintown:1039610768", "artists": ["ZEKE"], "startDate": "2026-10-15"}
        future_bad = {"id": "future-wrong-zeke", "bandsintownArtistId": "32942", "startDate": "2026-12-01"}
        good = {"id": "manual:flavor-fest-2026-friday-concerts", "artists": ["ZEKE"], "startDate": "2026-11-06"}
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source, history = root / "events.json", root / "event-history.json"
            source.write_text(json.dumps([bad, future_bad, good]))
            history.write_text(json.dumps({"events": [{"archiveKey": archive.archive_key(bad), "event": bad}]}))
            with patch.object(archive, "EVENT_FILES", (source,)), patch.object(archive, "HISTORY_FILE", history), patch.object(archive, "git_event_snapshots", return_value=[("2026-10-12T00:00:00Z", [bad, future_bad, good])]):
                archive.main()
                archive.main()
            result = json.loads(history.read_text())
            self.assertEqual([good["id"]], [r["event"]["id"] for r in result["events"]])
            self.assertEqual(1, result["summary"]["totalArchived"])

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

    def test_past_archive_adds_yesterday_on_the_next_day(self) -> None:
        today = dt.datetime.now(past_archives.PACIFIC).date()
        events = []
        for days_ago in (0, 1):
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
        self.assertEqual(["show-1"], [event["id"] for event in selected])


if __name__ == "__main__":
    unittest.main()
