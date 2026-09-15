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


EVENT_ID = "revival-night-trinity-2026"
RUNTIME_ID = f"manual:{EVENT_ID}"
ARTISTS = [
    "Issac Mansfield",
    "Vennisay",
    "Kaden Jordan",
    "Scarlito Jr.",
    "J Reborn",
    "Dre Skywalker",
    "Gabriel Katon",
]
SPOTIFY_PROFILES = {
    "Vennisay": "https://open.spotify.com/artist/47fuPz0K0cyruPcpXiBo2W",
    "Scarlito Jr.": "https://open.spotify.com/artist/46UmMAKrHKTvwKAV5mrNsi",
    "J Reborn": "https://open.spotify.com/artist/6qDQ0Rnp9bj86ZcsI4UkEX",
    "Dre Skywalker": "https://open.spotify.com/artist/6qE9NgK1b0kDnGUnGVh4zS",
    "Gabriel Katon": "https://open.spotify.com/artist/5G1xrscxyvpYHX72E108iW",
}


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def base_id(event: dict) -> str:
    return str(event.get("id") or "").removeprefix("manual:")


class RevivalNightProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manual = load("config/manual-events.json")
        cls.events = load("events.json")
        cls.supplemental = load("supplemental-events.json")
        cls.artists = load("config/artists.json")

    def test_verified_event_is_the_only_october_23_trinity_record(self):
        manual = [event for event in self.manual if base_id(event) == EVENT_ID]
        runtime = [event for event in self.events if base_id(event) == EVENT_ID]
        supplemental = [event for event in self.supplemental if base_id(event) == EVENT_ID]
        self.assertEqual(1, len(manual))
        self.assertEqual(1, len(runtime))
        self.assertEqual([], supplemental)
        self.assertEqual(EVENT_ID, manual[0]["id"])
        self.assertEqual(RUNTIME_ID, runtime[0]["id"])

        for collection in (self.manual, self.events, self.supplemental):
            duplicates = [
                event for event in collection
                if event.get("startDate") == "2026-10-23"
                and "Kaden Jordan" in (event.get("artists") or [])
                and base_id(event) != EVENT_ID
            ]
            self.assertEqual([], duplicates)

    def test_event_details_match_the_official_eventbrite_listing(self):
        event = next(event for event in self.events if event.get("id") == RUNTIME_ID)
        expected = overrides.REVIVAL_NIGHT_EVENT
        for field in (
            "title", "startDate", "startTime", "endTime", "doorsTime",
            "performanceTime", "timezone", "venue", "address", "postalCode",
            "city", "state", "artists", "headliner", "headliners", "supportActs",
            "ticketUrl", "officialUrl", "image", "imageType", "price",
            "advertisedBilling", "sourceName",
        ):
            self.assertEqual(expected[field], event[field], field)
        self.assertTrue(event["lineupExplicit"])
        self.assertTrue(event["imageOverride"])

        artwork = ROOT / event["image"]
        self.assertTrue(artwork.is_file())
        self.assertGreater(artwork.stat().st_size, 100_000)

    def test_every_billed_artist_has_a_working_roster_profile(self):
        roster = {artist["name"]: artist for artist in self.artists}
        self.assertTrue(set(ARTISTS).issubset(roster))
        for name, spotify in SPOTIFY_PROFILES.items():
            self.assertEqual(spotify, roster[name]["spotifyProfile"])
            self.assertTrue(roster[name]["enabled"])
            self.assertTrue(roster[name]["sourceRegistryVerified"])

    def test_manual_seed_normalizes_and_static_merge_keeps_one_event(self):
        manual = next(event for event in self.manual if event.get("id") == EVENT_ID)
        normalized = update_events.normalize_manual_event(manual, "2026-09-15T10:53:04Z")
        self.assertIsNotNone(normalized)
        self.assertEqual(RUNTIME_ID, normalized["id"])
        self.assertEqual(ARTISTS, normalized["artists"])

        merged = build_seo_site.merge_events(self.events, self.supplemental)
        self.assertEqual(1, len([event for event in merged if base_id(event) == EVENT_ID]))

    def test_late_override_removes_provider_duplicates_and_is_idempotent(self):
        provider_duplicate = {
            "id": "bandsintown:108906647",
            "title": "Kaden Jordan at Trinity College",
            "startDate": "2026-10-23",
            "startTime": "19:00",
            "venue": "Trinity College",
            "city": "New Port Richey",
            "state": "FL",
            "artists": ["Kaden Jordan"],
            "headliner": "Kaden Jordan",
            "officialUrl": "https://www.bandsintown.com/e/108906647",
            "ticketUrl": "https://www.eventbrite.com/e/revival-night-tickets-1990009565179",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events = [*self.events, provider_duplicate]
            supplemental = [*self.supplemental, provider_duplicate]
            (root / "events.json").write_text(json.dumps(events), encoding="utf-8")
            (root / "supplemental-events.json").write_text(json.dumps(supplemental), encoding="utf-8")

            overrides.apply(root)
            first_events = (root / "events.json").read_text(encoding="utf-8")
            first_supplemental = (root / "supplemental-events.json").read_text(encoding="utf-8")
            overrides.apply(root)

            self.assertEqual(first_events, (root / "events.json").read_text(encoding="utf-8"))
            self.assertEqual(first_supplemental, (root / "supplemental-events.json").read_text(encoding="utf-8"))
            combined = json.loads(first_events) + json.loads(first_supplemental)
            matches = [event for event in combined if overrides.is_revival_night_duplicate(event)]
            self.assertEqual([RUNTIME_ID], [event["id"] for event in matches])


if __name__ == "__main__":
    unittest.main()
