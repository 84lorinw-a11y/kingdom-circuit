import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class September12Phase2Repairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seo = load_module("build_seo_site_phase2", ROOT / "scripts" / "build_seo_site.py")
        cls.events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
        cls.supplemental = json.loads((ROOT / "supplemental-events.json").read_text(encoding="utf-8"))

    def test_multiday_ranges_are_displayed(self):
        cases = {
            "Uprise Festival 2026": "Sep 11–12, 2026",
            "Fountain Fest WV 2026": "Sep 18–19, 2026",
            "Ark of Worship Gospel & Christian Music Festival 2026": "Oct 9–10, 2026",
        }
        all_events = self.events + self.supplemental
        for title, expected in cases.items():
            event = next(item for item in all_events if item.get("title") == title)
            self.assertIn(expected, self.seo.format_date(event))

    def test_mike_teezy_uses_exact_apple_time_without_utc_rollover(self):
        event = next(item for item in self.events if item.get("id") == "official:4e2fc5c7c02ab1d34b9e")
        self.assertEqual("18:00", event.get("startTime"))
        self.assertEqual("America/New_York", event.get("timezone"))
        self.assertNotIn("endDate", event)
        self.assertIn("ce.01a1c61a-49a9-4e19-b629-46bac43b4970", event.get("officialUrl", ""))

    def test_confirmed_zauntee_duplicates_are_retired(self):
        merged = {item.get("id"): item for item in self.supplemental if item.get("status") == "merged"}
        for retired_id, (canonical_id, doors, performance, _) in self.seo_import_merges().items():
            self.assertEqual(canonical_id, merged[retired_id].get("mergedIntoId"))
            canonical = next(item for item in self.events if item.get("id") == canonical_id)
            self.assertEqual(doors, canonical.get("doorsTime"))
            self.assertEqual(performance, canonical.get("performanceTime"))
            self.assertIn("Skema Boy", canonical.get("artists", []))

    @staticmethod
    def seo_import_merges():
        repairs = load_module("sep12_repairs_phase2", ROOT / "scripts" / "apply_sep12_live_audit_repairs.py")
        return repairs.ZAUNTEE_MERGES

    def test_directory_state_and_month_require_one_matching_show(self):
        script = (ROOT / "assets" / "artist-filter-fix.js").read_text(encoding="utf-8")
        self.assertIn("const matchesEventPair = shows.some", script)
        self.assertIn("monthKey(event?.startDate) === selectedMonth", script)
        self.assertNotIn("(!selectedState || cardStates.has(selectedState))", script)

    def test_static_builder_retains_browser_redirect_pages(self):
        merged = [item for item in self.supplemental if item.get("status") == "merged"]
        combined = self.seo.merge_events(self.events, self.supplemental)
        for retired in merged:
            retained = next(item for item in combined if item.get("id") == retired.get("id"))
            self.assertEqual("merged", retained.get("status"))


if __name__ == "__main__":
    unittest.main()
