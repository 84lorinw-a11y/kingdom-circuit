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


EVENT_ID = overrides.KB_DIAMONDBACK_EVENT_ID
RUNTIME_ID = f"manual:{EVENT_ID}"


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def base_id(event: dict) -> str:
    return str(event.get("id") or "").removeprefix("manual:")


class KBDiamondbackProductionTests(unittest.TestCase):
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
        matches = [event for event in combined if overrides.is_kb_diamondback_duplicate(event)]
        self.assertEqual([RUNTIME_ID], [event["id"] for event in matches])

    def test_event_details_match_the_official_venue_and_ticket_listings(self):
        event = next(event for event in self.events if event.get("id") == RUNTIME_ID)
        expected = overrides.KB_DIAMONDBACK_EVENT
        for field in (
            "title", "startDate", "startTime", "doorsTime", "timezone",
            "venue", "address", "postalCode", "city", "state", "artists",
            "headliner", "supportActs", "ticketUrl", "officialUrl", "image",
            "imageType", "imagePosition", "price", "ageRestriction",
            "advertisedBilling", "sourceName", "organizer", "firstSeen",
            "lastVerified",
        ):
            self.assertEqual(expected[field], event[field], field)

        self.assertTrue(event["lineupExplicit"])
        self.assertTrue(event["imageOverride"])
        source_urls = {source["url"] for source in event["sources"]}
        self.assertEqual(
            {
                overrides.KB_DIAMONDBACK_VENUE_URL,
                overrides.KB_DIAMONDBACK_TICKET_URL,
                overrides.KB_DIAMONDBACK_BANDSINTOWN_URL,
            },
            source_urls,
        )

    def test_full_resolution_official_image_is_local_and_valid(self):
        artwork = ROOT / overrides.KB_DIAMONDBACK_IMAGE
        self.assertTrue(artwork.is_file(), artwork)
        self.assertGreater(artwork.stat().st_size, 100_000)
        payload = artwork.read_bytes()
        self.assertEqual(b"RIFF", payload[:4])
        self.assertEqual(b"WEBP", payload[8:12])

    def test_manual_seed_normalizes_and_static_merge_keeps_one_event(self):
        manual = next(event for event in self.manual if event.get("id") == EVENT_ID)
        normalized = update_events.normalize_manual_event(manual, "2026-09-17T20:00:00Z")
        self.assertIsNotNone(normalized)
        self.assertEqual(RUNTIME_ID, normalized["id"])
        self.assertEqual(["KB", "Skema Boy"], normalized["artists"])

        merged = build_seo_site.merge_events(self.events, self.supplemental)
        matches = [event for event in merged if overrides.is_kb_diamondback_duplicate(event)]
        self.assertEqual([RUNTIME_ID], [event["id"] for event in matches])

    def test_late_override_removes_provider_duplicates_and_is_idempotent(self):
        provider_duplicate = {
            "id": "bandsintown:108921018",
            "title": "KB",
            "startDate": "2026-12-04",
            "startTime": "19:30",
            "venue": "Diamondback Music Hall",
            "city": "Belleville",
            "state": "MI",
            "artists": ["Skema Boy", "KB"],
            "headliner": "KB",
            "officialUrl": overrides.KB_DIAMONDBACK_BANDSINTOWN_URL,
            "ticketUrl": overrides.KB_DIAMONDBACK_TICKET_URL,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "events.json").write_text(
                json.dumps([*self.events, provider_duplicate]),
                encoding="utf-8",
            )
            (root / "supplemental-events.json").write_text(
                json.dumps([*self.supplemental, provider_duplicate]),
                encoding="utf-8",
            )

            overrides.apply(root)
            first_events = (root / "events.json").read_text(encoding="utf-8")
            first_supplemental = (root / "supplemental-events.json").read_text(encoding="utf-8")
            overrides.apply(root)

            self.assertEqual(first_events, (root / "events.json").read_text(encoding="utf-8"))
            self.assertEqual(
                first_supplemental,
                (root / "supplemental-events.json").read_text(encoding="utf-8"),
            )
            combined = json.loads(first_events) + json.loads(first_supplemental)
            matches = [event for event in combined if overrides.is_kb_diamondback_duplicate(event)]
            self.assertEqual([RUNTIME_ID], [event["id"] for event in matches])


if __name__ == "__main__":
    unittest.main()
