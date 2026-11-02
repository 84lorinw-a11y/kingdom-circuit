"""The U.S. source refresh must not erase approved Canadian primary records."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_events as collector


def canadian_show(**changes):
    event = {
        "id": "official:ant-lee-canadian-booking",
        "title": "Light Up The City",
        "country": "CA",
        "state": "SK",
        "city": "Lloydminster",
        "venue": "ACTS Church",
        "startDate": "2099-02-26",
        "endDate": "2099-02-27",
        "startTime": "19:00",
        "timezone": "America/Edmonton",
        "startDateTime": "2099-02-26T19:00:00-07:00",
        "artists": ["Ant Lee"],
        "authority": "official_event",
        "status": "scheduled",
        "firstSeen": "2098-12-01T12:00:00Z",
        "image": "assets/events/approved-canadian-flyer.jpg",
        "imageOverride": True,
    }
    return dict(event, **changes)


class CanadianPrimaryRetentionTests(unittest.TestCase):
    def test_main_refresh_retains_exact_canadian_payload_through_final_local_day(self):
        canadian = canadian_show()
        stale_us = dict(canadian, id="old-us", country="US", state="TX")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "ARTISTS_FILE": ("artists.json", []),
                "OFFICIAL_SOURCES_FILE": ("sources.json", []),
                "MANUAL_EVENTS_FILE": ("manual.json", []),
                "KNOWN_INSTAGRAM_POSTS_FILE": ("instagram.json", []),
                "ATTRACTION_CACHE_FILE": ("attractions.json", {}),
                "EVENTS_FILE": ("events.json", [canadian, stale_us]),
                "STATUS_FILE": ("status.json", {}),
            }
            paths = {}
            for variable, (name, data) in files.items():
                paths[variable] = root / name
                paths[variable].write_text(json.dumps(data))
            # It is already the 28th in UTC, but still the show's final date
            # according to the site's established Pacific rollover guard.
            with patch.multiple(collector, **paths), \
                 patch.object(collector, "now_utc", return_value=datetime(2099, 2, 28, 2, tzinfo=timezone.utc)), \
                 patch.object(collector.canadian_event_guard, "today_cutoff", return_value="2099-02-27"), \
                 patch.object(collector, "scan_instagram_index", return_value=([], {})), \
                 patch.dict("os.environ", {"TICKETMASTER_API_KEY": ""}):
                self.assertEqual(collector.main(), 0)
            self.assertEqual(json.loads(paths["EVENTS_FILE"].read_text()), [canadian])

    def test_expired_or_explicitly_inactive_canadian_rows_are_not_restored(self):
        rows = [canadian_show(status=status, id="inactive:" + status)
                for status in ("cancelled", "canceled", "postponed", "merged")]
        rows.append(canadian_show(id="expired", endDate="2099-02-25"))
        self.assertEqual(collector.preserve_canadian_existing([], rows, "2099-02-26"), [])
        self.assertEqual(collector.preserve_canadian_existing([], [canadian_show()], "2099-02-28"), [])

    def test_explicit_replacement_or_merge_is_not_overwritten(self):
        existing = canadian_show()
        cancelled = dict(existing, status="cancelled")
        merged = dict(existing, id="official:replacement", mergedFromIds=[existing["id"]])
        for fresh in (cancelled, merged):
            with self.subTest(replacement=fresh["id"], status=fresh["status"]):
                self.assertEqual(collector.preserve_canadian_existing([fresh], [existing], "2099-02-26"), [fresh])

    def test_country_aliases_survive_without_treating_california_as_canada(self):
        rows = [canadian_show(id="ca:" + country, country=country) for country in ("CA", "CAN", "Canada")]
        california = canadian_show(id="california", country="US", state="CA")
        result = collector.preserve_canadian_existing([], [*rows, california], "2099-02-26")
        self.assertEqual(result, rows)


if __name__ == "__main__":
    unittest.main()
