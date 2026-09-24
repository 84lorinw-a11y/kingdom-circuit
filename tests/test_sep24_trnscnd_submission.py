import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_trnscnd_submission as trnscnd
import build_seo_site


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class TrnscndSubmissionProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manual = load("config/manual-events.json")
        cls.events = load("events.json")
        cls.supplemental = load("supplemental-events.json")
        cls.artists = load("config/artists.json")
        cls.updates = load("config/verified-artist-registry-updates.json")

    def test_promoter_submission_is_one_durable_canonical_event(self):
        manual = [event for event in self.manual if trnscnd.event_collision(event)]
        runtime = [event for event in self.events if trnscnd.event_collision(event)]
        supplemental = [
            event for event in self.supplemental if trnscnd.event_collision(event)
        ]
        self.assertEqual([trnscnd.EVENT_ID], [event["id"] for event in manual])
        self.assertEqual(
            [trnscnd.RUNTIME_EVENT_ID], [event["id"] for event in runtime]
        )
        self.assertEqual([], supplemental)

    def test_verified_event_details_and_artwork_match_submission(self):
        event = next(
            event for event in self.events
            if event.get("id") == trnscnd.RUNTIME_EVENT_ID
        )
        for field in (
            "title",
            "startDate",
            "endDate",
            "startTime",
            "endTime",
            "timezone",
            "venue",
            "address",
            "postalCode",
            "city",
            "state",
            "artists",
            "advertisedBilling",
            "officialUrl",
            "ticketUrl",
            "image",
            "imageType",
        ):
            self.assertEqual(trnscnd.EVENT[field], event[field], field)
        self.assertTrue(event["lineupExplicit"])
        self.assertTrue(event["imageOverride"])
        self.assertEqual(7, len(event["advertisedBilling"]))

    def test_requested_artists_are_on_the_directory(self):
        artists = {row["name"]: row for row in self.artists}
        for name in trnscnd.PROFILED_ARTISTS:
            with self.subTest(name=name):
                self.assertIn(name, artists)
                self.assertTrue(artists[name].get("enabled"))

        updates = {row["name"]: row for row in self.updates}
        self.assertEqual(146, updates["NXTMIKE"]["rosterOrder"])
        self.assertEqual(
            [178, 179, 180],
            [updates[name]["rosterOrder"] for name in ("N!X", "D Riddick", "Howard Langford")],
        )

    def test_show_card_displays_the_entire_bill_without_broken_profiles(self):
        event = next(
            event for event in self.events
            if event.get("id") == trnscnd.RUNTIME_EVENT_ID
        )
        card = build_seo_site.event_card(event, self.artists)
        for name in trnscnd.FULL_LINEUP:
            with self.subTest(name=name):
                self.assertIn(name, card)
        for name in trnscnd.PROFILED_ARTISTS:
            self.assertIn(build_seo_site.artist_path(name), card)
        for name in ("Leah Dates", "Rolanda Carter", "DJ Smalls"):
            self.assertNotIn(build_seo_site.artist_path(name), card)

        schema = build_seo_site.event_schema(event)
        self.assertEqual(
            trnscnd.FULL_LINEUP,
            [performer["name"] for performer in schema["performer"]],
        )

    def test_refresh_workflows_reapply_the_submission(self):
        for relative in (
            ".github/workflows/update-and-deploy.yml",
            ".github/workflows/catalog-curation.yml",
        ):
            workflow = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("python scripts/apply_trnscnd_submission.py", workflow)


if __name__ == "__main__":
    unittest.main()
