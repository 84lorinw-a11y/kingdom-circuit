from datetime import date, datetime, timezone
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import catalog_clock as clock
import calendar_maintenance as maintenance
import national_discovery
import prune_past_events


def at(instant):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    return FixedDateTime


class CatalogClockTests(unittest.TestCase):
    def test_actual_pacific_day_at_utc_and_daylight_saving_boundaries(self):
        cases = {
            "2026-11-15T07:59:59+00:00": date(2026, 11, 14),
            "2026-11-15T08:00:00+00:00": date(2026, 11, 15),
            "2026-07-15T06:59:59+00:00": date(2026, 7, 14),
            "2026-07-15T07:00:00+00:00": date(2026, 7, 15),
            "2026-11-01T08:30:00+00:00": date(2026, 11, 1),
            "2026-11-01T09:30:00+00:00": date(2026, 11, 1),
            "2027-03-14T09:59:59+00:00": date(2027, 3, 14),
            "2027-03-14T10:00:00+00:00": date(2027, 3, 14),
            "2027-01-01T07:59:59+00:00": date(2026, 12, 31),
            "2027-01-01T08:00:00+00:00": date(2027, 1, 1),
            "2028-02-29T07:59:59+00:00": date(2028, 2, 28),
            "2028-02-29T08:00:00+00:00": date(2028, 2, 29),
            "2028-03-01T07:59:59+00:00": date(2028, 2, 29),
            "2028-03-01T08:00:00+00:00": date(2028, 3, 1),
        }
        with patch.dict(os.environ, {}, clear=True):
            for instant, expected in cases.items():
                with self.subTest(instant=instant), patch.object(clock, "datetime", at(datetime.fromisoformat(instant))):
                    self.assertEqual(expected, clock.catalog_date())

    def test_frozen_day_survives_midnight_and_is_shared_by_catalog_consumers(self):
        with patch.dict(os.environ, {"KC_CATALOG_DAY": "2026-11-14"}), \
                patch.object(clock, "datetime", at(datetime(2026, 11, 15, 10, tzinfo=timezone.utc))):
            self.assertEqual(date(2026, 11, 14), clock.catalog_date())
            self.assertEqual(date(2026, 11, 14), national_discovery.today())
            self.assertEqual("2026-11-14", prune_past_events.today_cutoff())

    def test_invalid_override_fails_instead_of_silently_changing_the_day(self):
        for value in ("", " ", "2026-2-01", "2026-02-30", "2026-11-15T00:00:00Z", "20261115", "2026-11-15\nOTHER=value"):
            with self.subTest(value=value), patch.dict(os.environ, {"KC_CATALOG_DAY": value}):
                with self.assertRaisesRegex(ValueError, "KC_CATALOG_DAY"):
                    clock.catalog_date()

    def test_independent_live_freshness_rejects_a_previous_frozen_day(self):
        instant = datetime(2026, 11, 15, 10, tzinfo=timezone.utc)
        with patch.dict(os.environ, {"KC_CATALOG_DAY": "2026-11-14"}), \
                patch.object(maintenance, "datetime", at(instant)):
            self.assertEqual("2026-11-15", maintenance.today())
            errors = maintenance.catalog_errors({
                "asOf": "2026-11-14",
                "shows": [{"path": "/event/fixture/", "date": "2026-11-20", "end": "2026-11-20"}],
            }, maintenance.today())
            self.assertTrue(any("asOf" in error for error in errors))

    def test_workflow_freezes_actual_pacific_day_and_preserves_existing_environment_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            environment = Path(tmp) / "github-env"
            environment.write_text("EXISTING=value\n")
            with patch.dict(os.environ, {"KC_CATALOG_DAY": "stale or invalid"}), \
                    patch.object(clock, "datetime", at(datetime(2026, 11, 15, 7, 59, tzinfo=timezone.utc))):
                clock.main(["--github-env", str(environment)])
            self.assertEqual("EXISTING=value\nKC_CATALOG_DAY=2026-11-14\n", environment.read_text())

    def test_frozen_clock_is_exported_for_receipt_job_even_without_a_live_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            environment, output = Path(tmp) / 'env', Path(tmp) / 'output'
            output.write_text('existing=kept\n')
            with patch.object(clock, 'datetime', at(datetime(2026, 11, 15, 7, 59, tzinfo=timezone.utc))):
                clock.main(['--github-env', str(environment), '--github-output', str(output)])
            self.assertEqual('KC_CATALOG_DAY=2026-11-14\n', environment.read_text())
            self.assertEqual('existing=kept\ncatalog_day=2026-11-14\n', output.read_text())

    def test_builder_import_uses_the_frozen_day_for_its_visibility_boundary(self):
        environment = dict(os.environ, KC_CATALOG_DAY="2027-01-01", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "-c",
            "import sys,json;sys.path.insert(0,'scripts');import build_seo_site as b;"
            "print(json.dumps([str(b.TODAY),str(b.VISIBILITY_CUTOFF),"
            "b.current({'startDate':'2026-12-31'}),b.current({'startDate':'2027-01-01'})]))"],
            cwd=ROOT, env=environment, text=True, capture_output=True, check=True)
        self.assertEqual(["2027-01-01", "2027-01-01", False, True], json.loads(result.stdout))

    def test_helper_is_available_in_package_imports(self):
        with patch.dict(os.environ, {"KC_CATALOG_DAY": "2026-11-15"}):
            package_clock = importlib.import_module("scripts.catalog_clock")
            self.assertEqual(date(2026, 11, 15), package_clock.catalog_date())

    def test_website_collector_keeps_pacific_today_after_utc_midnight(self):
        import collect_artist_website_events as collector
        current = {"id": "today", "startDate": "2026-11-14"}
        expired = {"id": "yesterday", "startDate": "2026-11-13"}
        with patch.dict(os.environ, {"KC_CATALOG_DAY": "2026-11-14"}), \
                patch.object(collector, "now_utc", return_value=datetime(2026, 11, 15, 2, tzinfo=timezone.utc)), \
                patch.object(collector, "robots_allows", return_value=True), \
                patch.object(collector, "collect_jsonld_source_from_html", return_value=[expired, current]), \
                patch.object(collector, "candidate_internal_pages", return_value=[]), \
                patch.object(collector, "bandsintown_profiles", return_value=[]), \
                patch.object(collector, "merge_events", side_effect=list):
            events, warnings = collector.collect_artist(
                {"name": "Example", "website": "https://example.org"},
                Mock(get_text=Mock(return_value="<html></html>")), {}, "2026-11-15T02:00:00Z")
        self.assertEqual([current], events)
        self.assertEqual([], warnings)

    def test_website_merger_uses_catalog_day_but_preserves_real_receipt_time(self):
        import merge_artist_website_events as merger
        with patch.dict(os.environ, {"KC_CATALOG_DAY": "2026-11-14"}), \
                patch.object(merger, "now_utc", return_value=datetime(2026, 11, 15, 2, tzinfo=timezone.utc)), \
                patch("private_events.apply"), patch("private_events.records", return_value=[]), \
                patch.object(merger, "load_json", side_effect=lambda path, default: default), \
                patch.object(merger, "finalize_events", return_value=[]) as finalize, \
                patch.object(merger, "write_json") as write:
            self.assertEqual(0, merger.main())
        self.assertEqual(2, finalize.call_count)
        self.assertTrue(all(call.args[2] == date(2026, 11, 14) for call in finalize.call_args_list))
        status = next(call.args[1] for call in write.call_args_list if call.args[0] == merger.STATUS_FILE)
        self.assertEqual("2026-11-15T02:00:00Z", status["artistWebsiteMergeAt"])

    def test_pinned_redesign_receives_the_same_catalog_day(self):
        import apply_production_redesign as redesign
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            script, output = base / "approved.py", base / "observed.txt"
            script.write_text("""from pathlib import Path
import sys
def card_source_key(card): return ('', '', '')
def clean_text(value): return value
def normalized_key(value): return value
def site_today(): raise AssertionError('Independent module clock was not replaced')
def main(): Path(sys.argv[1]).write_text(site_today().isoformat())
""")
            with patch.dict(os.environ, {"KC_CATALOG_DAY": "2027-01-01"}):
                redesign.main([str(script), str(output)])
            self.assertEqual("2027-01-01", output.read_text())


if __name__ == "__main__":
    unittest.main()
