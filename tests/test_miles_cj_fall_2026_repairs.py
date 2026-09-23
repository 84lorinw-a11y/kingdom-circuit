import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MilesCjFall2026RepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        cls.manual = json.loads((ROOT / "config" / "manual-events.json").read_text(encoding="utf-8"))
        cls.supplemental = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))
        cls.artists = json.loads((ROOT / "config" / "artists.json").read_text(encoding="utf-8"))

    def event(self, event_id):
        return next(row for row in self.events if row.get("id") == event_id)

    def test_florida_tour_stops_are_canonical(self):
        expected = {
            "manual:miles-minnick-black-box-north-miami-2026-11-05": ("2026-11-05", "18:30", "Black Box Media Miami", "North Miami"),
            "manual:miles-minnick-christlike-university-jacksonville-2026-11-07": ("2026-11-07", "19:00", "The Albatross", "Jacksonville"),
            "manual:miles-minnick-christlike-university-orlando-2026-11-08": ("2026-11-08", "19:00", "Conduit", "Winter Park"),
        }
        for event_id, values in expected.items():
            row = self.event(event_id)
            self.assertEqual(values, (row["startDate"], row["startTime"], row["venue"], row["city"]))
            self.assertEqual(["Miles Minnick", "Tommy Zuko", "CJ Emulous"], row["artists"])
            self.assertEqual("scheduled", row["status"])

    def test_stale_manual_listings_are_redirect_only(self):
        for event_id in (
            "manual:cj-emulous-new-mainstream-miami-2026-11-05",
            "manual:cj-emulous-new-mainstream-jacksonville-2026-11-08",
        ):
            row = self.event(event_id)
            self.assertEqual("merged", row["status"])
            self.assertTrue(row["mergedIntoId"].startswith("manual:miles-minnick-"))

    def test_imported_lineups_are_linked_to_all_three_artists(self):
        for event_id in ("bandsintown:108940329", "bandsintown:108940352", "bandsintown:108940372"):
            row = next(item for item in self.supplemental if item.get("id") == event_id)
            self.assertEqual(["Miles Minnick", "Tommy Zuko", "CJ Emulous"], row["artists"])

    def test_confirmed_times_and_cj_alias_are_present(self):
        expected = {
            "manual:cj-emulous-glo-concert-los-angeles-2026": "18:00",
            "manual:cj-emulous-christlike-christmas-berkeley-2026": "18:00",
            "manual:cj-emulous-christlike-christmas-felton-2026": "19:00",
            "manual:miles-cj-zion-ultra-lounge-chandler-2026": "19:00",
        }
        for event_id, start_time in expected.items():
            self.assertEqual(start_time, self.event(event_id)["startTime"])
        cj = next(row for row in self.artists if row.get("name") == "CJ Emulous")
        self.assertIn("CJ Emulous GLO.", cj["aliases"])
        registry = json.loads((ROOT / "config" / "verified-artist-registry-updates.json").read_text(encoding="utf-8"))
        registry_cj = next(row for row in registry if row.get("name") == "CJ Emulous")
        self.assertIn("CJ Emulous GLO.", registry_cj["aliases"])

    def test_automation_reapplies_repairs_before_committing(self):
        for relative_path in (
            ".github/workflows/catalog-curation.yml",
            ".github/workflows/ensure-verified-fall-shows.yml",
        ):
            workflow = (ROOT / relative_path).read_text(encoding="utf-8")
            repair = workflow.index("python scripts/apply_miles_cj_fall_2026_repairs.py")
            commit = workflow.index("git add")
            self.assertLess(repair, commit, relative_path)


if __name__ == "__main__":
    unittest.main()
