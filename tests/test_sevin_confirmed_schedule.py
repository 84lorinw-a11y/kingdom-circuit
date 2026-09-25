import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import apply_sevin_official_schedule as sevin


class SevinConfirmedScheduleTests(unittest.TestCase):
    def test_refresh_removes_stale_provider_records_and_is_idempotent(self):
        rows = [
            {"id": "collector:kansas", "artists": ["Sevin"], "startDate": "2026-09-26", "city": "Sponsor Kansas City", "state": "MO"},
            {"id": "collector:charlotte", "artists": ["Sevin"], "startDate": "2026-11-21", "city": "Charlotte", "state": "NC"},
            {"id": "collector:sacramento", "artists": ["Sevin"], "startDate": "2026-12-05", "city": "Sacramento", "state": "CA"},
            {"id": "collector:nashville", "artists": ["Sevin"], "startDate": "2026-10-24", "city": "Nashville", "state": "TN", "startTime": "20:00"},
        ]
        unrelated = {"id": "another-performance", "artists": ["Sevin"], "startDate": "2026-09-26", "city": "Another City", "state": "PA"}
        rows.append(unrelated)
        original = copy.deepcopy(rows)
        events, supplemental = sevin.normalize_schedule(rows, rows[:-1])
        self.assertEqual([unrelated], events)
        self.assertEqual(3, len(supplemental))
        self.assertEqual((events, supplemental), sevin.normalize_schedule(events, supplemental))
        self.assertEqual(original, rows)

    def test_confirmed_local_times_billing_and_nashville_identity(self):
        by_id = {event["id"]: event for event in sevin.SEVIN_EVENTS}
        millville = by_id["sevin-live-millville-2026-09-26"]
        nashville = by_id["sevin-live-nashville-2026-10-24"]
        self.assertEqual(("Dwelling Place Church", "125 N 2nd St", "Millville", "NJ", "America/New_York"),
                         tuple(millville[k] for k in ("venue", "address", "city", "state", "timezone")))
        self.assertEqual(("We Are Church Nashville", "1501 Hadley Ave", "Old Hickory", "TN", "America/Chicago"),
                         tuple(nashville[k] for k in ("venue", "address", "city", "state", "timezone")))
        for event in (millville, nashville):
            self.assertEqual("19:00", event["startTime"])
            self.assertEqual(["Sevin", "HOG MOB Dontae"], event["advertisedBilling"])
            self.assertEqual(["Sevin"], event["artists"])
            self.assertNotIn("110", event["price"])
            self.assertNotIn("doorsTime", event)
        self.assertEqual("2026-08-09T00:00:00Z", nashville["firstSeen"])
        self.assertIn("/event/sevin-live-concert-2026-10-24-nashville-76d537/", nashville["legacyEventPaths"])
        self.assertFalse(any(event["city"] in {"Sacramento", "Charlotte", "Kansas City", "Oahu"} for event in by_id.values()))

    def test_historical_san_diego_record_is_preserved(self):
        historical = next(event for event in sevin.SEVIN_EVENTS if event["startDate"] == "2026-08-29")
        self.assertEqual("San Diego", historical["city"])
        self.assertIn("1976534238113", historical["ticketUrl"])
        self.assertEqual(sevin.HISTORICAL_HOGMOB_URL, historical["officialUrl"])


if __name__ == "__main__":
    unittest.main()
