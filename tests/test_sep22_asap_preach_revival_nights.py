import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_verified_event_overrides as overrides
import build_seo_site
import update_events


EVENT_ID = overrides.ASAP_PREACH_REVIVAL_EVENT_ID
RUNTIME_ID = f"manual:{EVENT_ID}"


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def base_id(event: dict) -> str:
    return str(event.get("id") or "").removeprefix("manual:")


class ASAPPreachRevivalNightsProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manual = load("config/manual-events.json")
        cls.events = load("events.json")
        cls.supplemental = load("supplemental-events.json")

    def test_verified_event_is_published_once_from_the_durable_manual_seed(self):
        manual = [event for event in self.manual if base_id(event) == EVENT_ID]
        runtime = [event for event in self.events if base_id(event) == EVENT_ID]
        supplemental = [event for event in self.supplemental if base_id(event) == EVENT_ID]

        self.assertEqual([EVENT_ID], [event["id"] for event in manual])
        self.assertEqual([RUNTIME_ID], [event["id"] for event in runtime])
        self.assertEqual([], supplemental)

        combined = [*self.events, *self.supplemental]
        matches = [
            event for event in combined
            if overrides.is_asap_preach_revival_duplicate(event)
        ]
        self.assertEqual([RUNTIME_ID], [event["id"] for event in matches])

    def test_event_details_match_the_official_eventbrite_listing(self):
        event = next(event for event in self.events if event.get("id") == RUNTIME_ID)
        expected = overrides.ASAP_PREACH_REVIVAL_EVENT
        for field in (
            "title", "startDate", "endDate", "startTime", "endTime", "timezone",
            "venue", "address", "postalCode", "city", "state", "artists",
            "headliner", "supportActs", "advertisedBilling", "ticketUrl",
            "officialUrl", "image", "imageType", "price", "ageRestriction",
            "sourceName", "organizer", "firstSeen", "lastVerified",
        ):
            self.assertEqual(expected[field], event[field], field)

        self.assertTrue(event["lineupExplicit"])
        self.assertTrue(event["imageOverride"])
        self.assertEqual(["ASAP Preach"], event["artists"])
        self.assertEqual(
            ["ASAP Preach", "Dray Day Ministries"],
            event["advertisedBilling"],
        )
        self.assertIn("2000057247066", event["ticketUrl"])
        self.assertNotIn("aff=", event["ticketUrl"])

    def test_manual_seed_normalizes_and_static_merge_keeps_one_event(self):
        manual = next(event for event in self.manual if event.get("id") == EVENT_ID)
        normalized = update_events.normalize_manual_event(
            manual, "2026-09-22T22:10:30Z"
        )
        self.assertIsNotNone(normalized)
        self.assertEqual(RUNTIME_ID, normalized["id"])
        self.assertEqual(["ASAP Preach"], normalized["artists"])

        merged = build_seo_site.merge_events(self.events, self.supplemental)
        matches = [
            event for event in merged
            if overrides.is_asap_preach_revival_duplicate(event)
        ]
        self.assertEqual([RUNTIME_ID], [event["id"] for event in matches])

    def test_late_override_removes_provider_duplicates_and_is_idempotent(self):
        provider_duplicate = {
            "id": "eventbrite:2000057247066",
            "title": "Revival Nights",
            "startDate": "2026-11-21",
            "startTime": "18:00",
            "venue": "Franklin County Fairgrounds",
            "city": "Hilliard",
            "state": "OH",
            "artists": ["ASAP Preach"],
            "headliner": "ASAP Preach",
            "officialUrl": overrides.ASAP_PREACH_REVIVAL_URL,
            "ticketUrl": overrides.ASAP_PREACH_REVIVAL_URL,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "events.json").write_text(
                json.dumps([*self.events, provider_duplicate]), encoding="utf-8"
            )
            (root / "supplemental-events.json").write_text(
                json.dumps([*self.supplemental, provider_duplicate]), encoding="utf-8"
            )

            overrides.apply(root)
            first_events = (root / "events.json").read_text(encoding="utf-8")
            first_supplemental = (
                root / "supplemental-events.json"
            ).read_text(encoding="utf-8")
            overrides.apply(root)

            self.assertEqual(
                first_events, (root / "events.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                first_supplemental,
                (root / "supplemental-events.json").read_text(encoding="utf-8"),
            )
            combined = json.loads(first_events) + json.loads(first_supplemental)
            matches = [
                event for event in combined
                if overrides.is_asap_preach_revival_duplicate(event)
            ]
            self.assertEqual([RUNTIME_ID], [event["id"] for event in matches])


if __name__ == "__main__":
    unittest.main()
